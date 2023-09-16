set -ex

# check submodules
if [ ! -d social-network/src/wrk2/scripts/social-network ]; then
    echo "Submodules not initialized"
    echo "Please run 'git submodule update --init --recursive' first"
    exit 1
fi

# check SSH connections
for i in {1..5}; do
    if [ "$(ssh root@autothrottle-$i whoami)" != root ]; then
        echo "SSH connection to autothrottle-$i failed"
        echo "Please make sure the command 'ssh root@autothrottle-$i whoami' works"
        exit 1
    fi
done

# upload to master
rsync -avz evaluation.py flannel.yaml hotel-reservation requirements.txt setup-node.sh social-network traces train-ticket utils.py root@autothrottle-1:

# setup master
ssh root@autothrottle-1 ./setup-node.sh master

# download from master
mkdir -p tmp
rsync -avz root@autothrottle-1:join-command :kube-config tmp/

for i in {2..5}; do
    # upload to worker
    rsync -avz setup-node.sh worker-daemon.py tmp/join-command tmp/kube-config root@autothrottle-$i:

    # setup worker
    ssh root@autothrottle-$i ./setup-node.sh worker
done

# cleanup
rm tmp/join-command tmp/kube-config
rmdir tmp
