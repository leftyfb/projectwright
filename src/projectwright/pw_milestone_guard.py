#!/usr/bin/env python3
"""Explicit, fail-closed acceptance receipts for generic Hermes project milestones.

Verification is intentionally NOT inferred from checked task boxes. A human
runs `--approve` after selecting a bounded acceptance command; only successful
acceptance evidence can exclude a milestone from future AI planning.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pw_worker_journal import journal_path as worker_journal_path

ROW = re.compile(r'^\s*- \[([ x!])\] \*\*([A-Z]+\d+)\s+[—-]\s+([A-Z]+)\*\*\s*(.*)$')
HEADER = re.compile(r'^\s*#{2,6}\s+([A-Z][A-Z0-9]*-\d+(?:-[A-Z0-9]+)*)\s+[—-]\s+(.+)$', re.M)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scoped_tasks(queue: str, requirement: str, milestone: str):
    items = []
    prefix = f'{requirement} / {milestone}:'
    for line in queue.splitlines():
        m = ROW.match(line)
        if m and m[4].startswith(prefix):
            items.append({'id':m[2], 'kind':m[3], 'state':m[1]})
    return items


def _git_scoped_evidence_current(repo: Path, receipt: dict, head: str) -> bool:
    """Preserve a receipt across descendant commits only if its declared scope is unchanged.

    The recorded commit is immutable. A non-ancestor, an invalid path, or any Git
    command failure invalidates the receipt. No working-tree state is modified.
    """
    old = receipt.get('git_head')
    paths = receipt.get('scope_paths')
    if (receipt.get('scope_version') != 1 or not isinstance(old, str)
            or not re.fullmatch(r'[0-9a-f]{40,64}', old)
            or not isinstance(paths, list) or not paths
            or any(not _valid_scope_path(path) for path in paths)):
        return False
    try:
        ancestor = subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', old, head],
                                  capture_output=True, check=False)
        if ancestor.returncode != 0:
            return False
        diff = subprocess.run(['git', '--literal-pathspecs', '-C', str(repo), 'diff', '--quiet', old, head, '--', *paths],
                              capture_output=True, check=False)
        return diff.returncode == 0
    except (OSError, ValueError):
        return False


def _authorized_successor_commit(repo: Path, before: str, after: str, milestone: str,
                                 queue: str, policy: dict, journal: dict | None) -> bool:
    """Prove exactly one completed, scope-bounded successor COMMIT.

    A journal is only a live bridge while its milestone awaits approval. Once
    accepted, the successor receipt provides the persistent commit evidence.
    """
    if not isinstance(journal, dict) or journal.get('current_task') is not None:
        return False
    completed = journal.get('last_completed_task')
    if not isinstance(completed, dict) or completed.get('kind') != 'COMMIT':
        return False
    if completed.get('git_head_before') != before or completed.get('git_head_after') != after:
        return False
    return _scoped_successor(repo, before, after, milestone, queue, policy, completed.get('id'))


def _scoped_successor(repo: Path, before: str, after: str, milestone: str,
                      queue: str, policy: dict, task_id: str | None = None) -> bool:
    spec = policy.get('milestones', {}).get(milestone) if isinstance(policy, dict) else None
    if acceptance_policy_fingerprint(spec) is None:
        return False
    req = spec['requirement']
    tasks = scoped_tasks(queue, req, milestone)
    commits = [t for t in tasks if t['kind'] == 'COMMIT' and t['state'] == 'x']
    if not tasks or any(t['state'] != 'x' for t in tasks) or len(commits) != 1:
        return False
    if task_id is not None and commits[0]['id'] != task_id:
        return False
    if not all(re.fullmatch(r'[0-9a-f]{40}', h or '') for h in (before, after)) or before == after:
        return False
    try:
        # Exactly one non-merge commit, based on the previously approved HEAD.
        parent = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', after + '^'], text=True).strip()
        if parent != before:
            return False
        parents = subprocess.check_output(['git', '-C', str(repo), 'rev-list', '--parents', '-n', '1', after], text=True).split()
        if len(parents) != 2 or parents[1] != before:
            return False
        changed = subprocess.check_output(['git', '-C', str(repo), 'diff-tree', '--no-commit-id', '--name-only', '-r', after], text=True).splitlines()
        return bool(changed) and set(changed) <= set(spec['scope_paths'])
    except (OSError, subprocess.CalledProcessError, ValueError):
        return False


def _valid_scope_path(path: object) -> bool:
    if (not isinstance(path, str) or not path or path.startswith(('/', '-', ':'))
            or '\\' in path):
        return False
    parts = path.split('/')
    return all(p not in ('', '.', '..') for p in parts) and not any(c in path for c in '*?[]\x00\n\r')




def milestone_fingerprint(requirements: bytes, milestone: str) -> str | None:
    """Hash exactly one milestone heading and its section (not later siblings)."""
    try:
        content = requirements.decode('utf-8')
    except UnicodeDecodeError:
        return None
    lines = content.splitlines(keepends=True)
    matches = []
    for i, line in enumerate(lines):
        found = HEADER.match(line)
        if found and found.group(1) == milestone:
            matches.append(i)
    if len(matches) != 1:
        return None
    start = matches[0]
    depth = len(lines[start]) - len(lines[start].lstrip('#'))
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r'^#{1,' + str(depth) + r'}\s+', lines[i]):
            end = i
            break
    return sha(''.join(lines[start:end]).encode('utf-8'))


def acceptance_policy_fingerprint(spec: dict) -> str | None:
    if not isinstance(spec, dict) or set(spec) != {'requirement', 'command', 'scope_paths'}:
        return None
    requirement, cmd, paths = spec['requirement'], spec['command'], spec['scope_paths']
    if (not isinstance(requirement, str) or not re.fullmatch(r'[A-Z][A-Z0-9]*-\d+', requirement)
            or not isinstance(cmd, list) or not cmd or not all(isinstance(x, str) and x for x in cmd)
            or not isinstance(paths, list) or not paths or len(set(paths)) != len(paths)
            or not all(_valid_scope_path(x) for x in paths)):
        return None
    return sha(json.dumps(spec, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))


def _milestone_sections(requirements: str) -> list[tuple[str, int, int]]:
    """Return explicit milestone sections and reject duplicate headings."""
    lines = requirements.splitlines(keepends=True)
    found = []
    for index, line in enumerate(lines):
        match = HEADER.match(line)
        if match and re.search(r'-M\d+(?:-|$)', match.group(1)):
            found.append((match.group(1), index, len(line) - len(line.lstrip('#'))))
    if len({item[0] for item in found}) != len(found):
        raise ValueError('Duplicate milestone headings; correct requirements before scheduling')
    sections = []
    for position, (milestone, start, depth) in enumerate(found):
        end = len(lines)
        for index in range(start + 1, len(lines)):
            if re.match(r'^#{1,' + str(depth) + r'}\s+', lines[index]):
                end = index
                break
        sections.append((milestone, start, end))
    return sections


def embedded_acceptance_policy(requirements: str) -> dict | None:
    """Parse the documented, executable acceptance block in requirements.md.

    The only accepted source syntax is a ``#### Acceptance`` subsection beneath
    each milestone, containing exactly one ``Command`` code span and one or
    more ``Scope`` code spans. Commands become argv with ``shlex``; they are
    never passed to a shell.
    """
    sections = _milestone_sections(requirements)
    if not sections:
        return None
    milestones = {}
    present = 0
    for milestone, start, end in sections:
        lines = requirements.splitlines()[start:end]
        acceptance = [i for i, line in enumerate(lines)
                      if re.match(r'^#{4,6}\s+Acceptance\s*$', line)]
        if not acceptance:
            continue
        present += 1
        if len(acceptance) != 1:
            raise ValueError(f'Duplicate Acceptance sections for {milestone}')
        acceptance_start = acceptance[0]
        acceptance_depth = len(lines[acceptance_start]) - len(lines[acceptance_start].lstrip('#'))
        acceptance_end = len(lines)
        for index in range(acceptance_start + 1, len(lines)):
            if re.match(r'^#{1,' + str(acceptance_depth) + r'}\s+', lines[index]):
                acceptance_end = index
                break
        body = lines[acceptance_start + 1:acceptance_end]
        commands = []
        scopes = []
        for line in body:
            if not line.strip():
                continue
            command_match = re.fullmatch(r'\s*-\s+\*\*Command:\*\*\s+`([^`]+)`\s*', line)
            scope_match = re.fullmatch(r'\s*-\s+\*\*Scope:\*\*\s+`([^`]+)`\s*', line)
            if command_match:
                commands.append(command_match.group(1))
            elif scope_match:
                scopes.append(scope_match.group(1))
            else:
                raise ValueError(f'Invalid Acceptance entry for {milestone}')
        if len(commands) != 1 or not scopes:
            raise ValueError(f'{milestone} Acceptance requires one Command and one or more Scope entries')
        try:
            command = shlex.split(commands[0], posix=True)
        except ValueError as exc:
            raise ValueError(f'Invalid acceptance command for {milestone}') from exc
        if (not command or any(not isinstance(part, str) or not part for part in command)
                or any(token in commands[0] for token in ('&&', '||', ';', '|', '>', '<', '$('))):
            raise ValueError(f'Acceptance Command must be a literal executable argv for {milestone}')
        spec = {'requirement': milestone.rsplit('-M', 1)[0],
                'command': command, 'scope_paths': scopes}
        if acceptance_policy_fingerprint(spec) is None:
            raise ValueError(f'Invalid acceptance policy for {milestone}')
        milestones[milestone] = spec
    if present and present != len(sections):
        missing = [milestone for milestone, _, _ in sections if milestone not in milestones]
        raise ValueError('Missing Acceptance section for milestone(s): ' + ', '.join(missing))
    return {'version': 1, 'milestones': milestones} if present else None


def validate_requirements(requirements: str, *, strict: bool = True,
                          project_dir: Path | None = None) -> dict:
    """Return first-run diagnostics without raising on user-authored Markdown.

    Acceptance sections are mandatory only in strict sequencing mode. Strict
    projects may keep their acceptance policy in the legacy JSON file instead.
    """
    issues = []
    lines = requirements.splitlines()
    requirement_re = re.compile(r'^\s*##\s+([A-Z][A-Z0-9]*-\d+)\s+[—-]\s+.+$')
    milestone_re = re.compile(r'^\s*###\s+([A-Z][A-Z0-9]*-\d+(?:-[A-Z0-9]+)*)\s+[—-]\s+.+$')
    requirement_ids = {m.group(1) for line in lines if (m := requirement_re.match(line))}
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith('##') and not line.lstrip().startswith('###'):
            candidate = re.match(r'^\s*##\s+([A-Z][A-Z0-9]*-\d+)\b', line)
            if candidate and not requirement_re.match(line):
                issues.append({'code': 'malformed_requirement_heading', 'line': number,
                               'requirement': candidate.group(1),
                               'message': f'Requirement heading {candidate.group(1)} must use ## {candidate.group(1)} — title'})
    if not requirement_ids and not any(issue['code'] == 'malformed_requirement_heading' for issue in issues):
        issues.append({'code': 'missing_requirement_heading',
                       'message': 'Add a requirement heading such as ## DEMO-1 — Goal'})
    milestones = []
    malformed_milestones = []
    for number, line in enumerate(lines, 1):
        match = milestone_re.match(line)
        if match and re.search(r'-M\d+(?:-|$)', match.group(1)):
            milestone = match.group(1)
            milestones.append((milestone, number))
            if milestone.rsplit('-M', 1)[0] not in requirement_ids:
                issues.append({'code': 'missing_requirement_heading', 'line': number,
                               'milestone': milestone,
                               'message': f'Missing requirement heading for {milestone}'})
        elif re.search(r'\b[A-Z][A-Z0-9]*-\d+-M\d+\b', line) and line.lstrip().startswith('#'):
            malformed_id = line.lstrip('# ').split()[0]
            malformed_milestones.append((malformed_id, number))
            issues.append({'code': 'malformed_milestone_heading', 'line': number,
                           'milestone': malformed_id,
                           'message': f'Milestone heading {malformed_id} must use ### {malformed_id} — title'})
    all_milestones = sorted(milestones + malformed_milestones, key=lambda item: item[1])
    milestone_requirement_ids = {milestone.rsplit('-M', 1)[0] for milestone, _ in milestones}
    for requirement_id in sorted(requirement_ids - milestone_requirement_ids):
        issues.append({'code': 'missing_milestone_heading', 'requirement': requirement_id,
                       'message': f'Requirement {requirement_id} defines no milestone headings'})
    seen = set()
    for milestone, line_number in all_milestones:
        if milestone in seen:
            issues.append({'code': 'duplicate_milestone_heading', 'line': line_number,
                           'milestone': milestone, 'message': f'Duplicate milestone heading: {milestone}'})
        seen.add(milestone)
    has_acceptance_like = any(re.match(r'^\s*#{4,6}\s+Acceptance\b', line) for line in lines)
    legacy_policy = None
    legacy_path = Path(project_dir) / 'telegram_acceptance.json' if project_dir is not None else None
    if has_acceptance_like and legacy_path is not None and legacy_path.is_file():
        issues.append({'code': 'duplicate_acceptance_policy_sources',
                       'message': 'Embedded and telegram_acceptance.json policies conflict; remove one source'})
    elif strict and not has_acceptance_like and project_dir is not None:
        if legacy_path is not None and legacy_path.is_file():
            legacy_error = None
            try:
                legacy_policy = policy_for_project(Path(project_dir))
            except ValueError as exc:
                legacy_error = str(exc)
            if legacy_error is None and legacy_policy is None:
                legacy_error = 'telegram_acceptance.json is missing or invalid for strict milestone acceptance'
            if legacy_error is not None:
                issues.append({'code': 'invalid_acceptance_policy', 'message': legacy_error})
    for index, (milestone, line_number) in enumerate(all_milestones):
        start = line_number
        end = len(lines)
        if index + 1 < len(all_milestones):
            end = all_milestones[index + 1][1] - 1
        body = lines[start:end]
        acceptance_indexes = [i for i, line in enumerate(body)
                              if re.match(r'^#{4,6}\s+Acceptance\s*$', line)]
        if not acceptance_indexes:
            if not strict and not any(re.match(r'^\s*#{4,6}\s+Acceptance\b', line) for line in body):
                continue
            if strict and legacy_policy is not None:
                spec = legacy_policy.get('milestones', {}).get(milestone)
                match = re.match(r'^(.*)-M\d+(?:-|$)', milestone)
                if (acceptance_policy_fingerprint(spec) is not None and match is not None
                        and spec['requirement'] == match.group(1)):
                    continue
                code = 'invalid_acceptance_policy' if spec is not None else 'missing_acceptance'
                message = (f'Invalid legacy acceptance policy for {milestone}' if spec is not None
                           else f'Missing legacy acceptance policy for {milestone}')
            else:
                code = 'missing_acceptance'
                message = f'Missing Acceptance section or strict legacy policy for {milestone}'
            issues.append({'code': code, 'line': line_number, 'milestone': milestone,
                           'message': message})
            continue
        if len(acceptance_indexes) != 1:
            issues.append({'code': 'duplicate_acceptance', 'line': line_number,
                           'milestone': milestone,
                           'message': f'Duplicate Acceptance sections for {milestone}'})
            continue
        acceptance = acceptance_indexes[0]
        acceptance_depth = len(body[acceptance]) - len(body[acceptance].lstrip('#'))
        acceptance_end = len(body)
        for index in range(acceptance + 1, len(body)):
            if re.match(r'^#{1,' + str(acceptance_depth) + r'}\s+', body[index]):
                acceptance_end = index
                break
        command_values, scope_values = [], []
        for entry in body[acceptance + 1:acceptance_end]:
            if not entry.strip():
                continue
            command_match = re.fullmatch(r'\s*-\s+\*\*Command:\*\*\s+`([^`]+)`\s*', entry)
            scope_match = re.fullmatch(r'\s*-\s+\*\*Scope:\*\*\s+`([^`]+)`\s*', entry)
            if command_match:
                command_values.append(command_match.group(1))
            elif scope_match:
                scope_values.append(scope_match.group(1))
            else:
                issues.append({'code': 'invalid_acceptance_entry', 'line': line_number,
                               'milestone': milestone, 'message': f'Invalid Acceptance entry for {milestone}'})
        if len(command_values) != 1:
            issues.append({'code': 'missing_acceptance_command' if not command_values else 'invalid_acceptance_command',
                           'line': line_number, 'milestone': milestone,
                           'message': f'{milestone} Acceptance requires exactly one Command'})
        else:
            raw_command = command_values[0]
            try:
                command = shlex.split(raw_command)
            except ValueError:
                command = []
            if (not command or any(token in raw_command for token in ('&&', '||', ';', '|', '>', '<', '$('))):
                issues.append({'code': 'invalid_acceptance_command', 'line': line_number,
                               'milestone': milestone,
                               'message': f'Acceptance Command must be a literal executable argv for {milestone}'})
        if not scope_values:
            issues.append({'code': 'missing_acceptance_scope', 'line': line_number,
                           'milestone': milestone, 'message': f'{milestone} Acceptance requires one or more Scope entries'})
        if len(set(scope_values)) != len(scope_values):
            issues.append({'code': 'invalid_acceptance_scope', 'line': line_number,
                           'milestone': milestone,
                           'message': f'{milestone} Acceptance Scope entries must be unique'})
        for scope in scope_values:
            if not _valid_scope_path(scope):
                issues.append({'code': 'invalid_acceptance_scope', 'line': line_number,
                               'milestone': milestone,
                               'message': f'Acceptance Scope must be a literal relative path: {scope}'})
    for issue in issues:
        milestone = issue.get('milestone')
        if isinstance(milestone, str) and '-M' in milestone:
            issue.setdefault('requirement', milestone.rsplit('-M', 1)[0])
    return {'valid': not issues, 'issues': issues, 'milestones': [m for m, _ in milestones]}


def policy_for_project(project_dir: Path) -> dict | None:
    project_dir = Path(project_dir)
    config_path = project_dir / 'config.json'
    embedded = None
    configured_requirements = False
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text())
            requirements_path = config.get('planning', {}).get('requirements_file')
            if isinstance(requirements_path, str) and requirements_path:
                requirements_path = Path(requirements_path).expanduser()
                if not requirements_path.is_absolute():
                    requirements_path = project_dir / requirements_path
                if requirements_path.is_file():
                    embedded = embedded_acceptance_policy(requirements_path.read_text(encoding='utf-8'))
                configured_requirements = True
            else:
                configured_requirements = False
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            raise ValueError('Invalid embedded milestone acceptance definitions')
    if embedded is None and not configured_requirements:
        fallback = project_dir / 'requirements.md'
        if fallback.is_file():
            embedded = embedded_acceptance_policy(fallback.read_text(encoding='utf-8'))
    path = project_dir / 'telegram_acceptance.json'
    if embedded is not None and path.is_file():
        raise ValueError('Duplicate acceptance policy sources; remove telegram_acceptance.json')
    if embedded is not None:
        return embedded
    if not path.is_file():
        return None
    try:
        policy = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if (not isinstance(policy, dict) or policy.get('version') != 1
            or not isinstance(policy.get('milestones'), dict)):
        return None
    return policy


def current_receipts(planning_state: dict, requirements: bytes, queue: str, head: str,
                     *, repo: Path | None = None, strict: bool = False, policy: dict | None = None,
                     journal: dict | None = None) -> dict:
    """Validate receipts against requirements, tasks and evidenced Git history.

    Earlier receipts can survive an authorized successor milestone commit in
    either sequencing mode. Unscoped legacy receipts remain HEAD-strict.
    """
    output = {}
    records = planning_state.get('verified_milestones', {})
    if not isinstance(records, dict):
        return output
    valid_base = {}
    for key, r in records.items():
        if not isinstance(r, dict):
            continue
        req, milestone = r.get('requirement_id'), r.get('milestone_id')
        if not isinstance(req, str) or not isinstance(milestone, str):
            continue
        items = scoped_tasks(queue, req, milestone)
        if strict:
            spec = policy.get('milestones', {}).get(milestone) if isinstance(policy, dict) else None
            requirements_ok = (
                milestone_fingerprint(requirements, milestone) is not None
                and r.get('milestone_requirements_sha256') == milestone_fingerprint(requirements, milestone)
                and acceptance_policy_fingerprint(spec) is not None
                and r.get('acceptance_policy_sha256') == acceptance_policy_fingerprint(spec)
                and spec.get('requirement') == req
                and r.get('acceptance_command') == spec.get('command')
                and r.get('scope_paths') == spec.get('scope_paths')
            )
        else:
            requirements_ok = r.get('requirements_sha256') == sha(requirements)
        if not (key == milestone and requirements_ok
                and items and all(x['state'] == 'x' for x in items)
                and [x['id'] for x in items] == r.get('completed_task_ids')
                and r.get('acceptance_exit_code') == 0):
            continue
        valid_base[milestone] = r
        if r.get('git_head') == head:
            output[milestone] = r
        elif repo is not None and _git_scoped_evidence_current(Path(repo), r, head):
            output[milestone] = r
    if repo is None or not isinstance(policy, dict):
        return output
    # Evidence chain: accepted successors supply their pinned commit, and one
    # unapproved final successor may use the worker's completed COMMIT journal.
    try:
        sequence = [m.group(1) for m in HEADER.finditer(requirements.decode('utf-8'))
                    if re.search(r'-M\d+(?:-|$)', m.group(1))]
    except UnicodeDecodeError:
        return output
    if len(set(sequence)) != len(sequence):
        return output
    for i, milestone in enumerate(sequence):
        if milestone in output or milestone not in valid_base:
            continue
        receipt = valid_base[milestone]
        # A legacy unscoped receipt cannot be safely carried forward. In
        # default mode also require the original acceptance scope and command
        # to still match the configured milestone policy.
        spec = policy.get('milestones', {}).get(milestone)
        if (acceptance_policy_fingerprint(spec) is None
                or receipt.get('scope_version') != 1
                or receipt.get('scope_paths') != spec['scope_paths']
                or receipt.get('acceptance_command') != spec['command']):
            continue
        cursor = receipt.get('git_head')
        if not isinstance(cursor, str):
            continue
        for successor in sequence[i + 1:]:
            if successor in valid_base:
                next_head = valid_base[successor].get('git_head')
                if not isinstance(next_head, str) or not _scoped_successor(Path(repo), cursor, next_head, successor, queue, policy):
                    break
                cursor = next_head
            elif _authorized_successor_commit(Path(repo), cursor, head, successor, queue, policy, journal):
                cursor = head
                break
            else:
                break
        if cursor == head:
            output[milestone] = valid_base[milestone]
    return output


def milestone_ids(requirements: str) -> set[str]:
    # Explicit milestone headings only; don't infer IDs from incidental body text.
    return {m.group(1) for m in HEADER.finditer(requirements) if re.search(r'-M\d+(?:-|$)', m.group(1))}


def approve(cfg: dict, project_dir: Path, requirement: str, milestone: str, test_command: list[str],
            scope_paths: list[str] | None = None, *, expected: dict | None = None):
    if not test_command:
        raise ValueError('Provide an acceptance command after -- (not a shell expression)')
    lock = Path(cfg['lock']).expanduser()
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a+') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        req_path = Path(cfg['planning']['requirements_file']).expanduser()
        req_bytes = req_path.read_bytes()
        req = req_bytes.decode('utf-8')
        if milestone not in milestone_ids(req):
            raise ValueError(f'Milestone heading not found: {milestone}')
        if not milestone.startswith(requirement + '-'):
            raise ValueError('Milestone is not part of the named requirement')
        if not re.search(r'(?m)^#{2,6}\s+' + re.escape(requirement) + r'\s+[—-]', req):
            raise ValueError('Requirement heading not found')
        queue_path = Path(cfg['queue']).expanduser()
        queue_bytes = queue_path.read_bytes()
        tasks = scoped_tasks(queue_bytes.decode('utf-8'), requirement, milestone)
        if not tasks or any(t['state'] != 'x' for t in tasks):
            raise ValueError('All milestone tasks must exist and be completed')
        if not any(t['kind'] == 'COMMIT' for t in tasks):
            raise ValueError('No completed COMMIT in milestone')
        cycle = Path(cfg['cycle_file']).expanduser()
        if cycle.exists():
            raise ValueError('Active Git cycle')
        journal_path = worker_journal_path(cfg, project_dir / 'config.json')
        if journal_path.exists() and json.loads(journal_path.read_text()).get('current_task') is not None:
            raise ValueError('Unresolved worker journal')
        repo = Path(cfg['worktree']).expanduser()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
        if git('branch', '--show-current') != cfg['branch'] or git('status', '--porcelain'):
            raise ValueError('Wrong branch or dirty repository')
        head = git('rev-parse', 'HEAD')
        scope_paths = scope_paths or []
        # Telegram approval must be bound to the exact evidence presented to
        # the operator. Check under the SAME lock that protects receipt writing.
        # This is additive; regular CLI approvals without `expected` still work.
        if expected is not None:
            if not isinstance(expected, dict):
                raise ValueError('Expected approval evidence must be an object')
            pinned = {
                'project': project_dir.name,
                'requirement': requirement,
                'milestone': milestone,
                'head': head,
                'requirements_sha256': sha(req_bytes),
                'queue_sha256': sha(queue_bytes),
                'task_ids': [t['id'] for t in tasks],
                'scope_paths': list(scope_paths),
                'command': list(test_command),
            }
            if cfg.get('planning', {}).get('milestone_sequence') == 'strict':
                policy_now = policy_for_project(project_dir)
                spec_now = (policy_now.get('milestones', {}).get(milestone)
                            if policy_now else None)
                pinned['milestone_requirements_sha256'] = milestone_fingerprint(req_bytes, milestone)
                pinned['acceptance_policy_sha256'] = acceptance_policy_fingerprint(spec_now)
            pending_path = project_dir / 'telegram_approval_pending.json'
            stored_request = json.loads(pending_path.read_text()) if pending_path.exists() else None
            if stored_request != expected:
                raise ValueError('Stale or missing pending approval record; no receipt recorded')
            reject_path = project_dir / 'telegram_approval_rejected.json'
            if reject_path.exists() and json.loads(reject_path.read_text()) == expected:
                raise ValueError('Milestone approval was explicitly rejected')
            if expected != pinned:
                raise ValueError('stale approval request: evidence changed; no receipt recorded')
            policy = policy_for_project(project_dir)
            if (not isinstance(policy, dict) or policy.get('version') != 1
                    or not isinstance(policy.get('milestones'), dict)
                    or policy['milestones'].get(milestone) != {
                        'requirement': requirement,
                        'command': list(test_command),
                        'scope_paths': list(scope_paths),
                    }):
                raise ValueError('stale Telegram acceptance policy; no receipt recorded')
        
        if scope_paths:
            if len(set(scope_paths)) != len(scope_paths) or any(not _valid_scope_path(p) for p in scope_paths):
                raise ValueError('Scope paths must be unique, relative, literal Git paths')
            for path in scope_paths:
                # Each path must match tracked files at approval, rather than silently
                # accepting an unrelated or nonexistent scope.
                tracked = subprocess.check_output(
                    ['git', '--literal-pathspecs', '-C', str(repo), 'ls-files', '--', path],
                    text=True).strip()
                if not tracked:
                    raise ValueError(f'Acceptance scope path is not tracked: {path}')
        # No shell: arguments remain explicit; prevent unintended external execution.
        command = subprocess.run(test_command, cwd=repo, capture_output=True, text=True,
                                 timeout=120, check=False)
        if command.returncode != 0:
            raise RuntimeError(f'Acceptance command failed ({command.returncode}): {(command.stderr or command.stdout)[-600:]}')
        if (queue_path.read_bytes() != queue_bytes or req_path.read_bytes() != req_bytes
                or git('rev-parse', 'HEAD') != head or git('status', '--porcelain')):
            raise RuntimeError('State changed during acceptance; no receipt recorded')
        state_path = project_dir / 'planning_state.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        strict = cfg.get('planning', {}).get('milestone_sequence') == 'strict'
        policy_spec = None
        if strict:
            current_policy = policy_for_project(project_dir)
            policy_spec = current_policy.get('milestones', {}).get(milestone) if current_policy else None
            if (acceptance_policy_fingerprint(policy_spec) is None
                    or policy_spec != {'requirement': requirement, 'command': list(test_command),
                                       'scope_paths': list(scope_paths)}):
                raise ValueError('Missing, invalid, or mismatched strict milestone acceptance policy')
            if milestone_fingerprint(req_bytes, milestone) is None:
                raise ValueError('Invalid or duplicated milestone section')
        records = dict(state.get('verified_milestones', {}))
        receipt = dict(requirement_id=requirement, milestone_id=milestone,
                       requirements_sha256=sha(req_bytes), git_head=head,
                       completed_task_ids=[t['id'] for t in tasks],
                       acceptance_command=test_command, acceptance_exit_code=0,
                       acceptance_output_sha256=sha((command.stdout + command.stderr).encode()),
                       approved_at=datetime.now(timezone.utc).isoformat())
        if strict:
            receipt['milestone_requirements_sha256'] = milestone_fingerprint(req_bytes, milestone)
            receipt['acceptance_policy_sha256'] = acceptance_policy_fingerprint(policy_spec)
        if scope_paths:
            # Record only explicitly validated scope. Without scope, the
            # receipt retains the conservative exact-HEAD behavior.
            receipt['scope_version'] = 1
            receipt['scope_paths'] = list(scope_paths)
        records[milestone] = receipt
        state['verified_milestones'] = records
        # Preserve other planning state; atomic replacement.
        import os, tempfile
        fd, tmp = tempfile.mkstemp(dir=project_dir, prefix='.planning_state.')
        try:
            with os.fdopen(fd, 'w') as out:
                json.dump(state, out, indent=2, sort_keys=True)
                out.write('\n')
                out.flush(); os.fsync(out.fileno())
            os.replace(tmp, state_path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
        return records[milestone]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--project', required=True)
    p.add_argument('--requirement', required=True)
    p.add_argument('--milestone', required=True)
    p.add_argument('--approve', action='store_true', required=True)
    p.add_argument('--scope-path', action='append', default=[], help='Tracked file or directory whose changes invalidate acceptance; repeat as needed')
    p.add_argument('command', nargs=argparse.REMAINDER)
    args = p.parse_args()
    if args.command and args.command[0] == '--': args.command.pop(0)
    root = Path.home() / '.hermes/projects' / args.project
    cfg = json.loads((root/'config.json').read_text())
    if cfg.get('id') != args.project: raise ValueError('Project ID mismatch')
    receipt = approve(cfg, root, args.requirement, args.milestone, args.command, args.scope_path)
    print(json.dumps({'decision':'milestone_verified', 'milestone':args.milestone,
                      'git_head':receipt['git_head'], 'task_ids':receipt['completed_task_ids']}, indent=2))

if __name__ == '__main__': main()
