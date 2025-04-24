import json
import os
import sys
import warnings

from keystoneauth1 import identity
from keystoneauth1.session import Session
from novaclient import client as NovaClient

from placementclient.client import Client


if not sys.warnoptions:
    warnings.simplefilter("ignore")

OS_AUTH_URL = os.environ.get("OS_AUTH_URL", "https://127.0.0.1:5000/v3")
OS_USERNAME = os.environ.get("OS_USERNAME", "admin")
OS_USER_DOMAIN_NAME = os.environ.get("OS_USER_DOMAIN_NAME", "Default")
OS_PASSWORD = os.environ.get("OS_PASSWORD", "")
OS_PROJECT_NAME = os.environ.get("OS_PROJECT_NAME", "admin")
OS_PROJECT_DOMAIN_NAME = os.environ.get("OS_PROJECT_DOMAIN_NAME", "Default")

MAKE_CHANGES = False
MAKE_DELETE = False
if len(sys.argv) > 1:
   MAKE_CHANGES = sys.argv[1] == '--fix'
   MAKE_DELETE = sys.argv[1] == '--delete'

auth = identity.v3.Password(
    auth_url=OS_AUTH_URL, username=OS_USERNAME,
    project_name=OS_PROJECT_NAME, password=OS_PASSWORD,
    user_domain_name=OS_USER_DOMAIN_NAME, project_domain_name=OS_PROJECT_DOMAIN_NAME)

sess = Session(auth=auth, verify=False)

p = Client(session=sess, version='1.32', interface='internal')
n = NovaClient.Client('2.60', session=sess)

vms = list(n.servers.list(search_opts=dict(all_tenants=True)))

r = [(r["name"], r["uuid"]) for r in p.resource_providers.list()]
rps = dict(r)
r = [(r["uuid"], r["name"]) for r in p.resource_providers.list()]
rrps = dict(r)

alls = {}
for rp in rps.values():
    c = p.http_client.get('/resource_providers/{uuid}/allocations'.format(uuid=rp))
    for cons,al in c['allocations'].items():
        alls.setdefault(cons, []).append({rp: al})        

for vm in vms:
    c = p.http_client.get('allocations/' + vm.id)
    host = vm.to_dict().get('OS-EXT-SRV-ATTR:host')
    if not host:
        continue
    rp = rps[host]
    changes_required = False
    if rp not in c['allocations']:
        changes_required = True
        print("VM {} on host {}({})\n - has no allocation on the host".format(vm.id, host, rp))
    if c['allocations'] and c['allocations'].pop(rp, None):
        print("VM {} on host {}({}) (generation {})".format(vm.id, host, rp, c.get('consumer_generation')))
    changes_required = changes_required or bool(c['allocations'])
    for arp, alloc in c['allocations'].items():
        print(" - has extra allocation on {}({}): {}".format(rrps[arp], arp, alloc))
    if MAKE_CHANGES and changes_required:
        new_alloc = {rp: dict(resources={'MEMORY_MB': vm.memory_mb, 'VCPU': vm.vcpus })}
        req = {'allocations': new_alloc, 'project_id': vm.tenant_id, 'user_id': vm.user_id, 'consumer_generation': c.get('consumer_generation', 1)}
        p.http_client.put('allocations/' + vm.id, headers={'content-type': 'application/json'}, data=json.dumps(req))
        print(' VM allocation has been fixed')
    alls.pop(vm.id, None)
print('')

if alls:
   print('Extra allocations found for unexisting VMs or uncompleted migrations:')
for k,v in alls.items():
    print(' - {} consumer has allocations:\n     {}'.format(k, '\n     '.join(['on {}({}): {}'.format(rrps[kk], kk, a) for kka in v for kk,a in kka.items()])))
    if MAKE_DELETE:
        p.http_client.delete('allocations/' + k, headers={'content-type': 'application/json'})
        print('     and it was deleted')

