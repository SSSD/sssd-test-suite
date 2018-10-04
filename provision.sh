SSH_ARGS="-o UserKnownHostsFile=/dev/null -o IdentitiesOnly=yes -o ControlMaster=auto -o ControlPersist=60s"
INVENTORY="./provision/inventory.yml"
PLAYBOOK="./provision/prepare-guests.yml"

if [[ "x$1" == "x-h" || "x$1" == "x--help" ]]; then
    echo "provision.sh [PLAYBOOK LIMIT PARAMS]"
    echo "  PLAYBOOKS: [playbook paths] ... playbooks to run"
    echo "  LIMIT: [all|list of host] ... limit which hosts should be provisioned"
    echo "  PArAMS: additional parameters to ansible-playbook"
    echo ""
    exit 0
fi

PLAYBOOK=${1-$PLAYBOOK}
LIMIT=${2-all}
PARAMS=${@:3}

echo "Executing playbook $PLAYBOOK"

ANSIBLE_HOST_KEY_CHECKING="false" ANSIBLE_SSH_ARGS="$SSH_ARGS" \
ansible-playbook                                               \
  --limit "$LIMIT"                                             \
  --inventory-file="$INVENTORY"                                \
  $PARAMS                                                      \
  $PLAYBOOK

if [ $? -ne 0 ]; then
    echo "Playbook execution failed!"
    exit 1
fi

exit 0
