# Autothrottle: A Practical Bi-Level Approach to Resource Management for SLO-Targeted Microservices
Autothrottle is a bi-level leraning-assisted resource management framework for SLO-targeted microservices published in NSDI '24. It architecturally decouples mechanisms of application SLO feedback and service resource control, and bridges them with the notion of performance targets. This decoupling enables targeted control policies for these two mechanisms, where we combine lightweight heuristics and learning techniques.

## Getting started
Due to the complexity of installing and configuring Kubernetes, variations in different environments can often cause some scripts to fail. To minimize the impact of environmental differences and facilitate the reproducibility of our evaluation, we automated almost all installation and configuration steps and provided scripts which can be run with one command. For hardware requirements, we specified all precise details to create Azure VMs to ensure that the environment can be replicated as closely as possible. While these requirements are not mandatory, if you wish to reproduce the evaluation results in a different environment, you will need to modify the relevant sections of the code accordingly.

Following the instructions below, you should be able to reproduce the results in Table 1 of our paper, except for the Sinan column, in less than 100 hours. Sinan is excluded because it has its own complex installation, configuration, and benchmarking process, which is not easy to automate and integrate with our scripts. If you want to produce other results or reuse our code in your own environment, please refer to the "Extending and modifying" section below.

### Hardware requirements
We use 5 Azure VMs to run the evaluation. To replicate the environment as closely as possible, you need to create 5 VMs following the instructions below. If you want to use different environments, please refer to the "Extending and modifying" section below.

- Basics
    - Project details: Choose as you like. **You may want to create a new resource group, since creating VMs will automatically create related resources which may be hard to clean up. Remember to delete the resource group to save money.**
    - Instance details
        - Virtual machine name: Use "autothrottle-1", ..., "autothrottle-5" for 5 VMs respectively.
        - Region: Choose the same region for all VMs. We use "(US) East US".
        - Availability options: "No infrastructure redundancy required".
        - Security type: "Standard".
        - Image: "Ubuntu Server 20.04 LTS - x64 Gen2".
        - VM architecture: "x64".
        - Run with Azure Spot discount: No.
        - Size: Choose "D32as_v5". It will show up as "Standard_D32as_v5 - 32 vcpus, 128 GiB memory (...)".
    - Administrator account: Choose as you like.
    - Inbound port rules
        - Public inbound ports: "Allow selected ports".
        - Select inbound ports: "SSH (22)".
- Disks
    - VM disk encryption: No.
    - OS disk
        - OS disk size: "256 GiB (P15)".
        - OS disk type: "Premium SSD (locally-redundant storage)".
        - Delete with VM: Yes.
        - Key management: "Platform-managed key".
        - Enable Ultra Disk compatibility: No.
    - Data disks: None.
    - Advanced: Leave as default.
- Networking: A new virtual network will be created when you create the first VM. Make sure to choose the same virtual network for all other VMs. **Especially when creating the second VM, you may need to wait for a while and refresh the page to see the virtual network created by the first VM, otherwise the system will automatically create another virtual network for you.** Leave other configurations as default.
- Management: Make sure auto-shutdown is disabled. Leave other configurations as default.
- Monitoring: Leave as default.
- Advanced: Leave as default.
- Tags: Choose as you like.

### Software requirements
We provide automated scripts to install and configure all necessary software. Please refer to `setup-all.sh`, `setup-node.sh`, `requirements.txt`, and other files for details.

1. First, clone this repository to your local machine and `cd` into it. Make sure to clone the `social-network/src` submodule as well by running `git submodule update --init --recursive`.
1. For each VM, depending on the authentication type you choose, set up SSH on your local machine so that commands like `ssh root@autothrottle-1 whoami` all work. Setting up in a way that you don't need to type password every time is recommended but not required.
1. Run `./setup-all.sh` on your local machine. It will upload all necessary files to the VMs and run `setup-node.sh` on them. We automated everything in these two scripts so that you can get exactly the same environment as we do with just one command. Read the comments in these two scripts to see what they do. This step should take about 10 minutes.
1. `ssh root@autothrottle-1` and check the output of `kubectl get nodes` and `kubectl get pods -A` to see if every node is ready and every pod is running. They should be ready and running in a few minutes.

### Run the evaluation script
1. `ssh root@autothrottle-1`.
1. Start a `screen` or `tmux` session.
1. While not necessary, it is recommended to edit the `send_notification` function at the top of `evaluation.py`. This function will be called every time a benchmark finishes with short messages reporting the progress and results. You can use it to send the messages via IM, SMS, email, etc. The entire script contains 72 benchmarks, and each benchmark takes about 70 minutes. If a benchmark takes more than 2 hours, something is probably wrong.
1. You may also want to edit the bottom of `evaluation.py` to only run some applications. Each of the 3 applications has 24 benchmarks.
1. Run `venv/bin/python3 evaluation.py`. This step should take less than 100 hours. Everything is automated. The results will be sent with the `send_notification` function and saved in `result.csv` on `root@autothrottle-1`.

### Interpret the results
By default, the evaluation script will reproduce the results in Table 1 of our paper. Each application will run 12 warmup benchmarks first, before producing 12 results. Each result is the average number of CPU cores allocated in a benchmark, and should be about the same as the corresponding one in Table 1 of our paper since we use the same evaluation setup and method. However, due to the inherent randomness of complex systems, you may see different numbers, or even "N/A"s which mean the P99 latency failed to meet the SLO in some benchmarks. When this happens, you need to delete related paths on `root@autothrottle-1` and run the benchmark again.

We observed that Train-Ticket application is more unstable than the other two. It sometimes fails in the middle of a benchmark, which results in very low average RPS and allocation. Extra care is needed when running it, so we put it at the end of the default benchmark list.

## Troubleshooting
- The setup scripts are not designed to be idempotent. If they fail in the middle, you may need to manually fix the problem and run the remaining part.
- If a benchmark fails or is interrupted, the `locust` processes it spawned should be cleaned up automatically. However, you may need to run `kubectl delete -f <application>/1.json` manually (Social-Network has 2 JSON files, so it needs `kubectl delete -f social-network/2.json -f social-network/1.json` instead) to clean the Kubernetes cluster before running the benchmark again.
- The evaluation script will automatically skip benchmarks that have already been run. If you want to run a benchmark again, you need to delete the corresponding path on `root@autothrottle-1`.
- SSH into the root account of each VM and check the output of `kubectl get nodes` and `kubectl get pods -A` to see if every node is ready and every pod is running. If not, use `kubectl describe node <node-name>` and `kubectl describe pod -n <namespace> <pod-name>` to diagnose.
- SSH into the root account of `autothrottle-{2-4}` and check that there is exactly one `tmux` session running `./worker-daemon.py`. The setup script should have started it automatically. You need to make sure one `./worker-daemon.py` is running on each of these 4 VMs.
- The scripts specify the exact version of each Docker and Kubernetes component. Theses versions are tested to work together with the provided configuration. If you use different versions or configurations, or if some rare errors occur, you may need to SSH into the root account of each VM and check the output of `systemctl status docker`, `systemctl status kubelet`, `journalctl -xeu docker`, and `journalctl -xeu kubelet` to diagnose.
- You can always delete the Azure resource group to clean up everything. Remember to delete the resource group after you finish the evaluation to save money.

## Code structure
```
.
├── evaluation.py         # evaluation script, run on root@autothrottle-1
├── flannel.yaml          # used during Kubernetes setup
├── hotel-reservation     # Hotel-Reservation application
│   ├── 1.json            # specifies the pods to run on each node
│   ├── generate-json.js  # generates 1.json
│   └── locustfile.py     # used by Locust to generate workload
├── requirements.txt      # Python dependencies for evaluation.py and utils.py
├── setup-all.sh          # setup script, run on local machine
├── setup-node.sh         # used by setup-all.sh, run on each node
├── social-network        # Social-Network application
│   ├── 1.json            # specifies the pods to run on each node
│   ├── 2.json            # specifies more pods to run on each node
│   ├── generate-json.js  # generates 1.json and 2.json
│   ├── locustfile.py     # used by Locust to generate workload
│   └── src               # submodule containing the source code of Social-Network
├── traces                # workload traces
│   ├── bursty.txt        # Bursty workload
│   ├── diurnal-2.txt     # another diurnal workload used for warmup
│   ├── diurnal.txt       # Diurnal workload
│   └── noisy.txt         # Noisy workload
├── train-ticket          # Train-Ticket application
│   ├── 1.json            # specifies the pods to run on each node
│   ├── generate-json.js  # generates 1.json
│   └── locustfile.py     # used by Locust to generate workload
├── utils.py              # used by evaluation.py, contains Tower's implementation
└── worker-daemon.py      # runs on each node, contains Captain's implementation
```

## Extending and modifying
If you want to run Autothrottle in a different environment, or run different experiments, you need to make the following changes:

- If different versions of Ubuntu, Docker, or Kubernetes are used, you may need to modify the `utils.py` and `worker-daemon.py`. They contain some `kubectl` commands and some cgroup-related APIs that may be different in different versions.
- Change the worker names in `{application}/generate-json.js`, and decide which microservices run on which worker. You may also want to change the number of replicas of each microservice. Run `{application}/generate-json.js` to regenerate the JSON files.
- Make sure each node can resolve the other nodes' names and connect to port 12198, which is used by the worker daemon.
- Modify or don't use `setup-all.sh` and `setup-node.sh` to suit your needs.
- There are many hard-coded paths like `data/*`, `tmp/*`, `{application}/*`, or `/root/{application}/*`. Change them to suit your needs.
- Modify `nodes` in `evaluation.py` to match what you specified in `{application}/generate-json.js`. Also modify `deploy` functions to match the number of pods after `kubectl apply` the JSON files.
- Determine the RPS range and the worker count of `locust` for each application. Modify `trace_multiplier`, the constant workload's RPS in `traces_and_targets`, and the `workers` in `evaluation.py` accordingly. The `deploy` function in `hotel_reservation` also contains a RPS value and a worker count for its warmup phase.
- Modify `initial_limit` in `evaluation.py` to match the number of CPUs of each node.
- Run benchmarks with `const` scalers and `DummyTower` to collect data. Extract each microservice's CPU usage from the data and use k-means clustering to divide the microservices into 2 groups. Modify `target1components` in `evaluation.py` accordingly.
- Decide each application's SLO. Modify `slo` in `evaluation.py` accordingly.
- Add more targets to `traces_and_targets` in `evaluation.py`, and find the best target for each application, workload trace, and scaler. The best target is the one that can still meet the SLO with the lowest allocation.

## Third-party code in this repository
- `flannel.yaml` is based on [flannel v0.13.1-rc2](https://github.com/flannel-io/flannel/blob/v0.13.1-rc2/Documentation/kube-flannel.yml). We added SHA256 checksums to the image fields.
- `hotel-reservation/locustfile.py` is based on [Sinan's version](https://github.com/zyqCSL/sinan-local/blob/382e76d5370496276f186c7e0bc8938c5f692fe3/locust/src/hotel_rps_100.py) with some modifications.
- `social-network/locustfile.py` is based on [Sinan's version](https://github.com/zyqCSL/sinan-local/blob/382e76d5370496276f186c7e0bc8938c5f692fe3/locust/src/socialml_rps_1.py) with some modifications.
- `social-network/src` is a submodule forked from [Sinan's repository](https://github.com/zyqCSL/sinan-local/tree/382e76d5370496276f186c7e0bc8938c5f692fe3/benchmarks/socialNetwork-ml-swarm). See its git history for more.
- `traces` are derived from Twitter's (no longer available) and [Google's](https://github.com/google/cluster-data/blob/7b7b6bd981bfd1273556e215132d09029c3b5893/ClusterData2019.md) public data.
- `train-ticket/locustfile.py` is based on [PPTAM's version](https://github.com/pptam/pptam-tool/blob/629c2987f8241ff589aa218c7c8e08ebce2e0b41/design_trainticket/locustfile.py) with some modifications.

## Contributing

This project welcomes contributions and suggestions. Most contributions require you to
agree to a Contributor License Agreement (CLA) declaring that you have the right to,
and actually do, grant us the rights to use your contribution. For details, visit
https://cla.microsoft.com.

When you submit a pull request, a CLA-bot will automatically determine whether you need
to provide a CLA and decorate the PR appropriately (e.g., label, comment). Simply follow the
instructions provided by the bot. You will only need to do this once across all repositories using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/)
or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks
This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft’s Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party’s policies.
