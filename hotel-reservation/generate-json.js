#!/usr/bin/env node
'use strict';

const fs = require('fs');

const worker1 = 'autothrottle-2';
const worker2 = 'autothrottle-3';
const worker3 = 'autothrottle-4';
const worker4 = 'autothrottle-5';
const image_go = 'igorrudyk1/hotelreservation:latest@sha256:cb64678950a01728551701f5782e34eef049e422f73eae7dcb69d7549682008c';
const image_consul = 'consul:1.15.4@sha256:362519540425cf077229da3851f3b80d622742dd81f1b2014863c044c2124ef3';
const image_jaeger = 'jaegertracing/all-in-one:latest@sha256:30238ffd383f266651cd4e0c36be67b6b0d3d882d0bbb67304c39af9ee61a4ef';
const image_mongo = 'mongo:4.4.6@sha256:6efa052039903e731e4a5550c68a13c4869ddc93742c716332883fd9c77eb79b';
const image_memcached = 'memcached:latest@sha256:8f8117a71c39d10d0ae0e1daf88d57619c99306fd4bd06e5270d962be0d607f9';

function labels(name) {
  return {
    'io.kompose.service': name,
  };
}

function env(o) {
  return Object.entries(o).map(([name, value]) => ({ name, value }));
}

function deployment(name, { strategy, nodeName, containers, hostname, volumes }) {
  return {
    apiVersion: 'apps/v1',
    kind: 'Deployment',
    metadata: {
      annotations: {
        'kompose.cmd': 'kompose convert',
        'kompose.version': '1.22.0 (955b78124)',
      },
      creationTimestamp: null,
      labels: labels(name),
      name,
      namespace: 'hotel-reservation',
    },
    spec: {
      replicas: 1,
      selector: {
        matchLabels: labels(name),
      },
      strategy,
      template: {
        metadata: {
          annotations: {
            'kompose.cmd': 'kompose convert',
            'kompose.version': '1.22.0 (955b78124)',
            'sidecar.istio.io/statsInclusionPrefixes': 'cluster.outbound,cluster_manager,listener_manager,http_mixer_filter,tcp_mixer_filter,server,cluster.xds-grp,listener,connection_manager',
            'sidecar.istio.io/statsInclusionRegexps': 'http.*'
          },
          creationTimestamp: null,
          labels: labels(name),
        },
        spec: {
          nodeName,
          containers,
          hostname,
          restartPolicy: 'Always',
          volumes,
        },
      },
    },
    status: {},
  };
}

function service(name, { serviceType, ports }) {
  return {
    apiVersion: 'v1',
    kind: 'Service',
    metadata: {
      annotations: {
        'kompose.cmd': 'kompose convert',
        'kompose.version': '1.22.0 (955b78124)',
      },
      creationTimestamp: null,
      labels: labels(name),
      name,
      namespace: 'hotel-reservation',
    },
    spec: {
      type: serviceType,
      ports,
      selector: labels(name),
    },
    status: {
      loadBalancer: {},
    },
  };
}

function persistent_volume(name, { storageClassName, hostPath }) {
  return {
    apiVersion: 'v1',
    kind: 'PersistentVolume',
    metadata: {
      name,
      namespace: 'hotel-reservation',
    },
    spec: {
      volumeMode: 'Filesystem',
      accessModes: ['ReadWriteOnce'],
      capacity: { storage: '1Gi' },
      storageClassName,
      hostPath: {
        path: hostPath,
        type: 'DirectoryOrCreate',
      },
    },
  };
}

function persistent_volume_claim(name, { storageClassName }) {
  return {
    apiVersion: 'v1',
    kind: 'PersistentVolumeClaim',
    metadata: {
      name,
      namespace: 'hotel-reservation',
    },
    spec: {
      accessModes: ['ReadWriteOnce'],
      storageClassName,
      resources: {
        requests: {
          storage: '1Gi',
        },
      },
    },
  };
}

function deployment_service(name, { strategy, nodeName, containers, hostname, volumes, serviceType, ports }) {
  return [
    deployment(name, { strategy, nodeName, containers, hostname, volumes }),
    service(name, { serviceType, ports }),
  ];
}

function go(nodeName, name, command, port) {
  return deployment_service(name, {
    nodeName,
    containers: [
      {
        name,
        image: image_go,
        command: [command],
        ports: [
          { containerPort: port },
        ],
      },
    ],
    ports: [
      { name: port.toString(), port, targetPort: port },
    ],
  });
}

function memcached(nodeName, name) {
  return deployment_service(name, {
    nodeName,
    containers: [
      {
        name,
        image: image_memcached,
        env: env({
          MEMCACHED_CACHE_SIZE: '128',
          MEMCACHED_THREADS: '2',
        }),
        ports: [
          { containerPort: 11211 }
        ],
      },
    ],
    ports: [
      { name, port: 11211, targetPort: 11211 },
    ],
  });
}

function mongodb(nodeName, name, serviceName) {
  var hostname = serviceName + '-db'
  var storageClassName = serviceName + '-storage';
  var volumeName = serviceName + '-pv'
  var claimName = serviceName + '-pvc'
  return [
    ...deployment_service(name, {
      strategy: { type: 'Recreate' },
      nodeName,
      containers: [
        {
          name,
          image: image_mongo,
          ports: [
            { containerPort: 27017 },
          ],
          volumeMounts: [
            { mountPath: '/data/db', name: serviceName }
          ],
        },
      ],
      hostname,
      volumes: [
        {
          name: serviceName,
          persistentVolumeClaim: { claimName },
        },
      ],
      ports: [
        { name, port: 27017, targetPort: 27017 },
      ],
    }),
    persistent_volume(volumeName, {
      storageClassName,
      hostPath: '/data/volumes/' + volumeName,
    }),
    persistent_volume_claim(claimName, { storageClassName }),
  ];
}

const doc = {
  apiVersion: 'v1',
  kind: 'List',
  items: [

    {
      apiVersion: 'v1',
      kind: 'Namespace',
      metadata: {
        name: 'hotel-reservation',
        labels: labels('hotel-reservation'),
      },
    },

    ...deployment_service('consul', {
      nodeName: worker1,
      containers: [
        {
          name: 'consul',
          image: image_consul,
          ports: [
            { containerPort: 8300 },
            { containerPort: 8400 },
            { containerPort: 8500 },
            { containerPort: 53, protocol: 'UDP' },
          ],
        },
      ],
      ports: [
        { name: '8300', port: 8300, targetPort: 8300 },
        { name: '8400', port: 8400, targetPort: 8400 },
        { name: '8500', port: 8500, targetPort: 8500 },
        { name: '8600', port: 8600, targetPort: 53, protocol: 'UDP' },
      ],
    }),

    ...deployment_service('jaeger', {
      nodeName: worker1,
      containers: [
        {
          name: 'jaeger',
          image: image_jaeger,
          ports: [
            { containerPort: 14269 },
            { containerPort: 5778 },
            { containerPort: 14268 },
            { containerPort: 14267 },
            { containerPort: 16686 },
            { containerPort: 5775, protocol: 'UDP' },
            { containerPort: 6831, protocol: 'UDP' },
            { containerPort: 6832, protocol: 'UDP' },
          ],
        },
      ],
      serviceType: 'NodePort',
      ports: [
        { name: '14269', port: 14269, targetPort: 14269 },
        { name: '5778', port: 5778, targetPort: 5778 },
        { name: '14268', port: 14268, targetPort: 14268 },
        { name: '14267', port: 14267, targetPort: 14267 },
        { name: '16686', port: 16686, targetPort: 16686, nodePort: 30005 },
        { name: '5775', port: 5775, targetPort: 5775, protocol: 'UDP' },
        { name: '6831', port: 6831, targetPort: 6831, protocol: 'UDP' },
        { name: '6832', port: 6832, targetPort: 6832, protocol: 'UDP' },
      ],
    }),

    ...deployment_service('frontend', {
      nodeName: worker1,
      containers: [
        {
          name: 'frontend',
          image: image_go,
          command: ['frontend'],
          ports: [
            { containerPort: 5000 },
          ],
        },
      ],
      serviceType: 'NodePort',
      ports: [
        { name: '5000', port: 5000, targetPort: 5000, nodePort: 30001 },
      ],
    }),

    ...go(worker3, 'geo', 'geo', 8083),
    ...mongodb(worker3, 'mongodb-geo', 'geo'),

    ...go(worker4, 'profile', 'profile', 8081),
    ...memcached(worker4, 'memcached-profile'),
    ...mongodb(worker4, 'mongodb-profile', 'profile'),

    ...go(worker4, 'rate', 'rate', 8084),
    ...memcached(worker4, 'memcached-rate'),
    ...mongodb(worker4, 'mongodb-rate', 'rate'),

    ...go(worker2, 'recommendation', 'recommendation', 8085),
    ...mongodb(worker2, 'mongodb-recommendation', 'recommendation'),

    ...go(worker2, 'reservation', 'reservation', 8087),
    ...memcached(worker2, 'memcached-reserve'),
    ...mongodb(worker2, 'mongodb-reservation', 'reservation'),

    ...go(worker3, 'search', 'search', 8082),

    ...go(worker3, 'user', 'user', 8086),
    ...mongodb(worker3, 'mongodb-user', 'user'),

  ],
};

fs.writeFileSync('hotel-reservation/1.json', JSON.stringify(doc, null, 2) + '\n');
