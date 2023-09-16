import collections
import dataclasses
import datetime
import json
import lzma
import numpy
import pathlib
import random
import socket
import subprocess
import time
import traceback
import vowpalwabbit


def load_trace(p):
    return list(map(int, pathlib.Path(p).read_text().splitlines()))


def dump_trace(trace, p):
    pathlib.Path(p).write_text('\n'.join(map(str, trace)) + '\n')


def load_samples(path):
    path = pathlib.Path(path)
    with lzma.open(path/'stats.json.xz', 'rt') as f:
        stats = json.load(f)
    samples = []
    last_rps = None
    last_action = None
    last_action_p = None
    for t, d in stats['_tower']:
        if last_rps is not None:
            samples.append((last_rps, last_action, last_action_p, d['p99_latency'], d['allocation']))
            last_rps = None
            last_action = None
            last_action_p = None
        if 'action' in d:
            last_rps = d['rps']
            last_action = d['action']
            last_action_p = d['action_p']
    return samples


class DummyTower:
    def __call__(self, t, stats, scalers):
        return {}


class ExploreTower:
    def __init__(self, scaler, targets, target1components, samples=(), warmup=0):
        self.scaler = scaler
        self.targets = targets
        self.target1components = target1components
        self.explore_count = {i: 0 for i in range(len(self.targets) ** 2)}
        for i in samples:
            self.explore_count[i[1]] += 1
        self.stage = -warmup - 1
        self.action = None

    def __call__(self, t, stats, scalers):
        if self.stage < 0:
            self.stage += 1
            return {}

        if self.stage == 0:
            self.stage = 1
            min_explore_count = min(self.explore_count.values())
            actions_with_min_explore_count = [k for k, v in self.explore_count.items() if v == min_explore_count]
            print(f'{min_explore_count=}, {len(actions_with_min_explore_count)=}')
            self.action = random.choice(actions_with_min_explore_count)
            self.explore_count[self.action] += 1
            target1 = self.targets[self.action // len(self.targets)]
            target2 = self.targets[self.action % len(self.targets)]
            updates = {}
            for k, v in scalers.items():
                if v['type'] == self.scaler:
                    if k in self.target1components:
                        updates[k] = (target1,)
                    else:
                        updates[k] = (target2,)
            return updates

        if self.stage == 1:
            self.stage = 0
            stats['_tower']['action'] = self.action
            stats['_tower']['action_p'] = 1 / len(self.targets) ** 2
            return {}


class VwTower:
    learning_rate = 0.5

    def __init__(self, scaler, targets, target1components, slo, samples=(), explore=0.1, drop_samples=0, aggregate_samples=20):
        self.scaler = scaler
        self.targets = targets
        self.target1components = target1components
        self.slo = slo
        self.samples = list(samples)
        self.explore = explore
        self.drop_samples = drop_samples
        self.aggregate_samples = aggregate_samples
        self.last_rps = None
        self.last_action = None
        self.last_action_p = None

    def __call__(self, t, stats, scalers):
        if self.last_rps is not None:
            if self.drop_samples:
                self.drop_samples -= 1
            else:
                latency = stats['_tower']['p99_latency']
                allocation = stats['_tower']['allocation']
                self.samples.append((self.last_rps, self.last_action, self.last_action_p, latency, allocation))

        train_samples = list(self.samples)

        try:
            min_allocation = min(i[4] for i in train_samples if i[3] <= self.slo)
            max_allocation = max(i[4] for i in train_samples if i[3] <= self.slo)
        except ValueError:
            min_allocation = None
            max_allocation = None
        try:
            min_latency = min(i[3] for i in train_samples if i[3] > self.slo)
            max_latency = max(i[3] for i in train_samples if i[3] > self.slo)
        except ValueError:
            min_latency = None
            max_latency = None
        for i, (rps, action, action_p, latency, allocation) in enumerate(train_samples):
            if latency <= self.slo:
                try:
                    cost = (allocation - min_allocation) / (max_allocation - min_allocation)
                except ZeroDivisionError:
                    cost = 0.5
            else:
                try:
                    cost = (latency - min_latency) / (max_latency - min_latency) + 2
                except ZeroDivisionError:
                    cost = 2.5
            train_samples[i] = (rps, action, action_p, cost)

        def median(l):
            l = sorted(l)
            if not l:
                return None
            if len(l) % 2:
                return l[len(l) // 2]
            else:
                return (l[len(l) // 2 - 1] + l[len(l) // 2]) / 2
        sample_categories = collections.defaultdict(lambda: collections.defaultdict(list))
        for i in train_samples:
            action = i[1]
            rps = round(i[0] / self.aggregate_samples) * self.aggregate_samples
            sample_categories[action][rps].append(i)
        aggregated_samples = []
        for action in sample_categories:
            for rps in sample_categories[action]:
                aggregated_samples.append((rps, action, 1 / len(self.targets) ** 2, median(i[3] for i in sample_categories[action][rps])))
        train_samples = []
        if aggregated_samples:
            for i in range(10000):
                train_samples.append(random.choice(aggregated_samples))

        vw = vowpalwabbit.Workspace(f'--cb_explore {len(self.targets) ** 2} --epsilon 0 -l {self.learning_rate} --nn 3 --quiet')
        for rps, action, action_p, cost in train_samples:
            vw.learn(f'{action+1}:{cost}:{action_p} | rps:{rps}')

        rps = stats['_tower']['rps']
        distribution = vw.predict(f'| rps:{rps}')
        action = numpy.random.choice(len(distribution), p=numpy.array(distribution) / sum(distribution))
        action_p = distribution[action]

        vw.finish()

        if action_p == 1:
            stats['_tower']['explore'] = action
            distribution = [0] * len(self.targets) ** 2
            distribution[action] += 1 - self.explore
            explore_actions = []
            x = action // len(self.targets)
            y = action % len(self.targets)
            if x - 1 >= 0:
                explore_actions.append(action - len(self.targets))
            if x + 1 < len(self.targets):
                explore_actions.append(action + len(self.targets))
            if y - 1 >= 0:
                explore_actions.append(action - 1)
            if y + 1 < len(self.targets):
                explore_actions.append(action + 1)
            for i in explore_actions:
                distribution[i] += self.explore / len(explore_actions)
            action = numpy.random.choice(len(distribution), p=numpy.array(distribution) / sum(distribution))
            action_p = distribution[action]

        stats['_tower']['action'] = action
        stats['_tower']['action_p'] = action_p
        self.last_rps = rps
        self.last_action = action
        self.last_action_p = action_p

        target1 = self.targets[action // len(self.targets)]
        target2 = self.targets[action % len(self.targets)]
        updates = {}
        for k, v in scalers.items():
            if v['type'] == self.scaler:
                if k in self.target1components:
                    updates[k] = (target1,)
                else:
                    updates[k] = (target2,)

        return updates


def kubectl_apply(k8s_json, namespace, pod_count):
    def all_ready(output):
        l = output.splitlines()
        if len(l) != pod_count:
            return False
        for i in l:
            name, phase = i.split()
            if phase == 'Running':
                continue
            if phase == 'Succeeded':
                if name.startswith('jaeger-cassandra-schema-'):
                    continue
            return False
        return True

    if not isinstance(k8s_json, list):
        k8s_json = [k8s_json]
    for i, p in enumerate(k8s_json):
        if i:
            time.sleep(60)
        subprocess.run(['kubectl', 'apply', '-f', p],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, check=True)
    while True:
        p = subprocess.run(['kubectl', 'get', 'pods', f'-n={namespace}',
            r'-o=jsonpath={range .items[*]}{.metadata.name} {.status.phase}{"\n"}{end}'],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True, check=True)
        if all_ready(p.stdout):
            return
        time.sleep(1)


def kubectl_delete(k8s_json, namespace):
    if not isinstance(k8s_json, list):
        k8s_json = [k8s_json]
    for i, p in enumerate(reversed(k8s_json)):
        if i:
            time.sleep(60)
        subprocess.run(['kubectl', 'delete', '-f', p],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, check=True)
    while True:
        p = subprocess.run(['kubectl', 'get', 'pods', f'-n={namespace}',
            r'-o=jsonpath={range .items[*]}{.metadata.name} {.status.phase}{"\n"}{end}'],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True, check=True)
        if p.stdout == '':
            return
        time.sleep(1)


def with_locust(temp_dir, locustfile, url, workers):
    args = [
        'locust',
        '--worker',
        '-f', locustfile,
    ]
    worker_ps = []
    for i in range(workers):
        worker_ps.append(subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL))

    args = [
        'locust',
        '--master',
        '--expect-workers', f'{workers}',
        '--headless',
        '-f', locustfile,
        '-H', url,
        '--csv', temp_dir/'locust',
        '--csv-full-history',
    ]
    master_p = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

    time.sleep(1)
    return master_p, worker_ps


def parse_locust_stats_history(temp_dir):
    with (temp_dir/'locust_stats_history.csv').open('r') as f:
        result = []
        last_t = None
        _, _, _, _, _, _, *percentile_headers, _, _, _, _, _, _, _ = f.readline().split(',')
        percentile_headers = [f'p{i[:-1]}_latency' for i in percentile_headers]
        for line in f:
            timestamp, _, type_, name, rps, _, *percentiles, _, _, _, _, _, _, _ = line.split(',')
            timestamp = int(timestamp)
            if timestamp != last_t:
                last_t = timestamp
                result.append((timestamp, {}))
            if type_ == '' and name == 'Aggregated':
                for k, v in zip(percentile_headers, percentiles):
                    if v == 'N/A':
                        v = 0  # TODO
                    result[-1][1][k] = int(v) / 1e3
                result[-1][1]['rps'] = float(rps)
            else:
                result[-1][1][f'rps-{type_}-{name}'] = float(rps)
        return result


def benchmark(output_dir, namespace, locustfile, url, nodes, deploy, teardown, scalers, tower, locust_workers):
    output_dir = pathlib.Path(output_dir)
    if output_dir.exists():
        print('skipped:', output_dir)
        return False

    print('start:', output_dir)
    pathlib.Path('request.log').unlink(missing_ok=True)
    deploy()

    node_sockets = {}
    for node, node_components in nodes.items():
        node_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        node_socket.connect((node, 12198))
        node_sockets[node] = node_socket.makefile('rw')
        node_sockets[node].write(json.dumps({
            'method': 'start',
            'namespace': namespace,
            'components': node_components,
            'scalers': {i: scalers[i] for i in node_components if i in scalers},
        }) + '\n')
        node_sockets[node].flush()
    for node_socket in node_sockets.values():
        line = node_socket.readline()
        data = json.loads(line)
        assert data['ok']
    print('all nodes started')

    time_ = datetime.datetime.utcnow().isoformat() + 'Z'
    temp_dir = pathlib.Path('tmp')/time_
    temp_dir.mkdir(parents=True, exist_ok=True)

    time.sleep(1)
    stats_history = collections.defaultdict(list)
    p, worker_ps = with_locust(temp_dir, locustfile, url, locust_workers)
    with p:
        try:
            time_base = time.time()
            monotonic_base = time.time() - time.perf_counter()
            locust_t = None
            while True:
                t = time.perf_counter()
                tt = (-t) % 1
                t += tt
                time.sleep(tt)
                if p.poll() is not None:
                    break

                stats = collections.defaultdict(dict)
                try:
                    locust_stats = parse_locust_stats_history(temp_dir)
                    if locust_stats[-1][0] != locust_t:
                        locust_t = locust_stats[-1][0]
                        stats['_tower'] = locust_stats[-1][1]
                except Exception:
                    print('parse_locust_stats_history failed')
                    traceback.print_exc()

                do_tower = False
                if stats:
                    do_tower = True
                    print('fetch all stats')
                    for node_socket in node_sockets.values():
                        node_socket.write(json.dumps({
                            'method': 'stats',
                        }) + '\n')
                        node_socket.flush()
                    local_stats = {}
                    for node_socket in node_sockets.values():
                        line = node_socket.readline()
                        data = json.loads(line)
                        assert data['ok']
                        local_stats.update(data['stats'])
                    allocation = 0
                    for component in scalers:
                        l = [i[1]['scaler.limit'] for i in local_stats[component]]
                        if l:
                            allocation += sum(l) / len(l)
                        else:
                            print('empty local stats')
                            do_tower = False
                    stats['_tower']['allocation'] = allocation
                    print('fetch all stats done')

                if do_tower:
                    tower_updates = tower(t, stats, scalers)
                    if tower_updates:
                        print('tower update')
                        for node_socket in node_sockets.values():
                            node_socket.write(json.dumps({
                                'method': 'update',
                                'update': tower_updates,
                            }) + '\n')
                            node_socket.flush()
                        for node_socket in node_sockets.values():
                            line = node_socket.readline()
                            data = json.loads(line)
                            assert data['ok']
                        print('tower update done')

                if '_tower' in stats:
                    print(stats['_tower'])
                for name in stats:
                    stats_history[name].append((t + monotonic_base, stats[name]))

        except Exception:
            traceback.print_exc()
            teardown()
            raise

    for node_socket in node_sockets.values():
        node_socket.write(json.dumps({
            'method': 'stop',
        }) + '\n')
        node_socket.flush()
    for node_socket in node_sockets.values():
        line = node_socket.readline()
        data = json.loads(line)
        assert data['ok']
        for k, v in data['stats'].items():
            assert k not in stats_history
            stats_history[k] = v

    for p in worker_ps:
        p.wait()

    stats_history_relative_time = {k: [(t - time_base, v) for t, v in l] for k, l in stats_history.items()}
    with lzma.open(temp_dir/'stats.json.xz', 'wt') as f:
        json.dump(stats_history_relative_time, f)

    with lzma.open(temp_dir/'request.log.xz', 'wt') as fo:
        with open('request.log', 'rt') as fi:
            for line in fi:
                data = json.loads(line)
                data['time'] += monotonic_base - time_base
                fo.write(json.dumps(data) + '\n')
    pathlib.Path('request.log').unlink()

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temp_dir.rename(output_dir)
    teardown()
    print('finished')
    return True


@dataclasses.dataclass(frozen=True)
class TimeSeries:
    # data must be sorted by time and is not checked
    def __init__(self, data):
        object.__setattr__(self, 'data', tuple(data))

    def __repr__(self):
        return f'{type(self).__name__}({self.data})'

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, i):
        if isinstance(i, slice):
            return type(self)(self.data[i])
        if isinstance(i, int):
            return self.data[i]
        raise TypeError(f'indices must be integers or slices')

    def __len__(self):
        return len(self.data)

    # suitable for matplotlib plotting
    def columns(self):
        return tuple(zip(*self.data))

    def start(self):
        return self.data[0][0]

    def duration(self):
        return self.data[-1][0] - self.data[0][0]

    def offset(self, offset):
        return type(self)((t + offset, v) for t, v in self.data)

    def slice(self, start, stop):
        return type(self)((t, v) for t, v in self.data if start <= t < stop)

    def rate(self):
        return type(self)((t2, (v2 - v1) / (t2 - t1)) for (t1, v1), (t2, v2) in zip(self.data, self.data[1:]))

    def map(self, f):
        return type(self)((t, f(v)) for t, v in self.data)

    def diff(self):
        return type(self)((t2, v2 - v1) for (t1, v1), (t2, v2) in zip(self.data, self.data[1:]))

    def accum(self):
        data = []
        accum = 0
        for t, v in self.data:
            accum += v
            data.append((t, accum))
        return type(self)(data)

    def average(self):
        return sum(v for t, v in self.data) / len(self.data)

    def sum(self):
        return sum(v for t, v in self.data)

    # return the smallest value which >= percentage% of values
    # suitable for latency calculation
    def percentage(self, percentage):
        assert isinstance(percentage, int) and 0 <= percentage <= 100
        sorted_values = sorted(v for t, v in self.data)
        return sorted_values[(len(self.data) * percentage - 1) // 100]

    def downsample_with(self, interval, f):
        groups = collections.defaultdict(list)
        for t, v in self.data:
            groups[int(round(t, 1) / interval)].append(v)
        return type(self)(((t + 1) * interval, f(l)) for t, l in sorted(groups.items()))

    def downsample_first(self, interval):
        return self.downsample_with(interval, lambda l: l[0])

    def downsample_last(self, interval):
        return self.downsample_with(interval, lambda l: l[-1])

    def downsample_average(self, interval):
        return self.downsample_with(interval, lambda l: sum(l) / len(l))

    def downsample_sum(self, interval):
        return self.downsample_with(interval, sum)

    def downsample_percentage(self, interval, percentage):
        assert isinstance(percentage, int) and 0 <= percentage <= 100
        return self.downsample_with(interval, lambda l: sorted(l)[(len(l) * percentage - 1) // 100])

    def downsample_time_weighted_average(self, interval):
        events = []
        for t, v in self.data:
            events.append((t, 'sample', v))
        t = self.data[0][0] // interval * interval + interval
        events.append((t, 'init'))
        t += interval
        while t < self.data[-1][0]:
            events.append((t, 'output'))
            t += interval
        events.sort()
        data = []
        state = []
        for event in events:
            if event[1] == 'sample':
                state.append((event[0], event[2]))
            elif event[1] == 'init':
                assert state
                state = [(event[0], state[-1][1])]
            elif event[1] == 'output':
                assert state
                state.append((event[0], state[-1][1]))
                integral = 0
                for i in range(len(state) - 1):
                    integral += state[i][1] * (state[i + 1][0] - state[i][0])
                data.append((event[0], integral / interval))
                state = [state[-1]]
        return type(self)(data)

    @classmethod
    def zip_with(cls, f, *args):
        state = [None] * len(args)
        events = []
        for i, series in enumerate(args):
            for t, v in series.data:
                events.append((t, i, v))
        events.sort()
        data = []
        for t, i, v in events:
            state[i] = v
            if all(s is not None for s in state):
                data.append((t, f(*state)))
        return cls(data)


def load_stats(path, k):
    path = pathlib.Path(path)
    with lzma.open(path/'stats.json.xz', 'rt') as f:
        stats = json.load(f)
    data = collections.defaultdict(list)
    for component, l in stats.items():
        for t, d in l:
            if k in d:
                data[component].append((t, d[k]))
    return {component: TimeSeries(l) for component, l in data.items()}


def load_cpu_limit(path):
    return load_stats(path, 'scaler.limit')


def load_cpu_usage(path):
    return {k: v.rate() for k, v in load_stats(path, 'cpu_usage').items()}


def load_nr_throttled(path):
    return {k: v.diff() for k, v in load_stats(path, 'cpu_stat.nr_throttled').items()}


def load_rps(path):
    return load_stats(path, 'rps')['_global']


def load_request_log(path):
    path = pathlib.Path(path)
    data = []
    with lzma.open(path/'request.log.xz', 'rt') as f:
        for line in f:
            data.append(json.loads(line))
    data.sort(key=lambda x: x['time'])
    return data


def load_request_latency(path):
    data = load_request_log(path)
    return TimeSeries([(i['time'], i['latency']) for i in data])
