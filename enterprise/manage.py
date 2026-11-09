"""Trusted provisioning CLI, requires a privileged DB credential and server terminal.

Never expose this module as HTTP or invoke it using untrusted web form parameters.
"""
from __future__ import annotations
import argparse
from sqlalchemy import select, func
from enterprise.database import session_factory
from enterprise.models import Project, Member, ActionItem
from enterprise.permissions import audited


def main():
    p = argparse.ArgumentParser(description='PEIMS trusted database provisioning')
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('create-project')
    a.add_argument('--id', required=True); a.add_argument('--title', required=True)
    a.add_argument('--currency', default='GHS')
    a.add_argument('--actor', required=True, help='Trusted administrative operator ID (audit metadata)')
    b = sub.add_parser('grant-member')
    b.add_argument('--project', required=True); b.add_argument('--subject', required=True)
    b.add_argument('--role', choices=['viewer','engineer','manager'], required=True)
    b.add_argument('--actor', required=True)
    c = sub.add_parser('revoke-member')
    c.add_argument('--project', required=True); c.add_argument('--subject', required=True)
    c.add_argument('--actor', required=True)
    args = p.parse_args()
    operator = args.actor.strip()
    if not operator or len(operator) > 255:
        p.error('A nonempty administrative actor ID is required')

    with session_factory()() as db:
        if args.command == 'create-project':
            project_id, title, currency = args.id.strip(), args.title.strip(), args.currency.strip().upper()
            if not project_id or len(project_id) > 64 or not title or len(title) > 200 or len(currency) != 3:
                p.error('Invalid project details')
            if db.get(Project, project_id):
                p.error('Project already exists')
            db.add(Project(id=project_id, title=title, currency=currency))
            db.flush()
            audited(db, project_id, operator, 'project.created', project_id, ['id','title','currency'])
        else:
            project = db.scalar(select(Project).where(Project.id == args.project).with_for_update())
            if project is None:
                p.error('Unknown project')
            subject = args.subject.strip()
            if not subject or len(subject) > 255:
                p.error('Invalid subject')
            x = db.get(Member, (args.project, subject))
            if args.command == 'grant-member':
                if x:
                    if x.role == 'manager' and args.role != 'manager':
                        count = db.scalar(select(func.count()).select_from(Member).where(
                            Member.project_id == args.project, Member.role == 'manager'))
                        if count <= 1:
                            p.error('Cannot demote final manager')
                    x.role = args.role
                    x.version += 1
                    event = 'member.role_changed'
                else:
                    db.add(Member(project_id=args.project, principal_sub=subject,
                                  role=args.role, version=1))
                    event = 'member.added'
                audited(db, args.project, operator, event, subject, ['role'])
            elif args.command == 'revoke-member':
                if x is None:
                    p.error('Member not found')
                if x.role == 'manager':
                    count = db.scalar(select(func.count()).select_from(Member).where(
                        Member.project_id == args.project, Member.role == 'manager'))
                    if count <= 1:
                        p.error('Cannot revoke final manager')
                assigned_count = db.scalar(select(func.count()).select_from(ActionItem).where(
                    ActionItem.project_id == args.project, ActionItem.assigned_sub == subject))
                if assigned_count:
                    p.error('Reassign action items before revoking member')
                db.delete(x)
                audited(db, args.project, operator, 'member.revoked', subject, ['membership'])
        db.commit()
    print('Provisioning command completed')


if __name__ == '__main__':
    main()
