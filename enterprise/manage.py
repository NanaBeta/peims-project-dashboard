"""Trusted machine/terminal provisioning; NEVER expose this command through HTTP."""
from __future__ import annotations
import argparse
from sqlalchemy.orm import Session
from enterprise.database import session_factory
from enterprise.models import Project,Member

def main():
    p=argparse.ArgumentParser(description='PEIMS trusted server-side provisioning (requires database access)')
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('create-project')
    a.add_argument('--id',required=True);a.add_argument('--title',required=True)
    a.add_argument('--currency',default='GHS')
    b=sub.add_parser('grant-member')
    b.add_argument('--project',required=True);b.add_argument('--subject',required=True)
    b.add_argument('--role',choices=['viewer','engineer','manager'],required=True)
    c=sub.add_parser('revoke-member')
    c.add_argument('--project',required=True);c.add_argument('--subject',required=True)
    args=p.parse_args()
    with session_factory()() as db:
        if args.command=='create-project':
            if not args.id.strip() or not args.title.strip() or len(args.currency)!=3:
                p.error('Invalid project details')
            if db.get(Project,args.id): p.error('Project already exists')
            db.add(Project(id=args.id,title=args.title,currency=args.currency.upper()))
        elif args.command=='grant-member':
            if not args.subject.strip() or not db.get(Project,args.project):p.error('Invalid subject or project')
            x=db.get(Member,(args.project,args.subject))
            if x:x.role=args.role
            else: db.add(Member(project_id=args.project,principal_sub=args.subject,role=args.role))
        elif args.command=='revoke-member':
            x=db.get(Member,(args.project,args.subject))
            if x:db.delete(x)
        db.commit()
    print('Provisioning command completed')

if __name__=='__main__':main()
