import os
import sys
import time
import warnings

from keystoneauth1 import identity
from keystoneauth1.session import Session
from novaclient import client as novaclient

warnings.warn = lambda *args, **kwargs: None

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f'Usage: python3 {sys.argv[0]} <ServerID> [<BackupName>]')
        sys.exit(100)

    for env_key in ['OS_AUTH_URL', 'OS_PASSWORD', 'OS_USERNAME']:
        if env_key not in os.environ:
            print(f'OpenStack credentials are required. "{env_key}" not found in ENV.')
            sys.exit(100)
    auth = identity.v3.Password(
        auth_url=os.environ['OS_AUTH_URL'],
        password=os.environ['OS_PASSWORD'],
        username=os.environ['OS_USERNAME'],
        user_domain_id=os.environ.get('OS_USER_DOMAIN_ID'),
        user_domain_name=os.environ.get('OS_USER_DOMAIN_NAME'),
        project_id=os.environ.get('OS_PROJECT_ID'),
        project_domain_id=os.environ.get('OS_PROJECT_DOMAIN_ID'),
        project_name=os.environ.get('OS_PROJECT_NAME'),
        project_domain_name=os.environ.get('OS_PROJECT_DOMAIN_NAME'),
    )

    sess = Session(auth=auth, verify=False)

    client = novaclient.Client('2.67', session=sess)
    server = client.servers.get(sys.argv[1])
    if len(sys.argv) < 3:
        info = server.manager._action(
            'getExportingInfo', server, {}
        )
        print(f'Export info:\n{info}\n')
        names = set()
        if info.get('task'):
            if info['task'].get('status', 'none') != 'none':
                names.add(info['task']['name'])
            else:
                print(f'Task is in "none" state, means it have been already finished')
        for snapshot in info.get('snapshots', []):
            print(f'Server has x-block-snapshot "{snapshot}"')
            names.add(snapshot)
    else:
        names = set([sys.argv[2]])

    for name in names:
        print(f'Stopping backup export "{name}"')
        server.manager._action(
            'finishBackupExporting', server, {"name": name,"success": False}
        )