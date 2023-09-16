#!/usr/bin/env node
'use strict';

const fs = require('fs');

const worker1 = 'autothrottle-2';
const worker2 = 'autothrottle-3';
const worker3 = 'autothrottle-4';
const worker4 = 'autothrottle-5';
const image_cpp = 'hypercube/social-network-ml-microservices:latest@sha256:1b8d25acb3137df320b80d7f9ccd55eb3bc8a1141fc57d78d57a978ce3e0d605';
const image_nginx = 'hypercube/social-network-ml-nginx:latest@sha256:6ac95749cb7aff055735ce490c7e702d1dabf8b6262c87d52d49b8ef4377833a';
const image_media_filter = 'hypercube/social-network-ml-media-filter:latest@sha256:ece820ae1156eab2c6b41eae07ecac524960d47bcdd4e063e9d3520399dcac05';
const image_text_filter = 'hypercube/social-network-ml-text-filter:latest@sha256:6f541847637a92e331f1088b78dcdf77acbe6242960994aabf1ced51dc308117';

const dnsmasq = {
  name: 'dnsmasq',
  image: 'janeczku/go-dnsmasq:release-1.0.7@sha256:3a99ad92353b55e97863812470e4f7403b47180f06845fdd06060773fe04184f',
  args: [
    '--listen',
    '127.0.0.1:53',
    '--default-resolver',
    '--append-search-domains',
  ],
};

function env(o) {
  return Object.entries(o).map(([name, value]) => ({name, value}));
}

function deployment(name, {nodeName, containers, podLabels}) {
  return {
    apiVersion: 'apps/v1',
    kind: 'Deployment',
    metadata: {
      namespace: 'social-network',
      name,
    },
    spec: {
      replicas: 1,
      selector: {
        matchLabels: podLabels || {name},
      },
      template: {
        metadata: {
          name,
          labels: podLabels || {name},
        },
        spec: {
          nodeName,
          containers,
          restartPolicy: 'Always',
          enableServiceLinks: false,
        },
      },
    },
  };
}

function service(name, {serviceType, ports, selector}) {
  return {
    apiVersion: 'v1',
    kind: 'Service',
    metadata: {
      namespace: 'social-network',
      name,
    },
    spec: {
      type: serviceType,
      ports,
      selector: selector || {name},
    },
  };
}

function deployment_service(name, {nodeName, containers, serviceType, ports}) {
  return [
    deployment(name, {nodeName, containers}),
    service(name, {serviceType, ports}),
  ];
}

function multi_deployment_service(name, nodeNames, {containers, serviceType, ports}) {
  return [
    ...nodeNames.map((nodeName, i) => deployment(`${name}-${i+1}`, {nodeName, containers, podLabels: {name, replicaId: `${i+1}`}})),
    service(name, {serviceType, ports}),
  ];
}

function cpp(nodeName, name, command) {
  return deployment_service(name, {
    nodeName,
    containers: [
      {
        name,
        image: image_cpp,
        command: [command],
      },
    ],
    ports: [
      {port: 9090},
    ],
  });
}

function memcached(nodeName, name) {
  return deployment_service(name, {
    nodeName,
    containers: [
      {
        name,
        image: 'memcached:1.6.0@sha256:95b8ef0e16a1f0b99d2d9c933afcc6caf395c4e33b281444b38d6951f4c2e3e8',
        env: env({
          MEMCACHED_CACHE_SIZE: '4096',
          MEMCACHED_THREADS: '8',
        }),
      },
    ],
    ports: [
      {port: 11211},
    ],
  });
}

function mongodb(nodeName, name) {
  return deployment_service(name, {
    nodeName,
    containers: [
      {
        name,
        image: 'mongo:4@sha256:90e9402437d0fafc818fde2cc108ccb445e02b0c85b230bcf3a55def0f0029ec',
        args: [
          '--nojournal',
          '--quiet',
        ],
      },
    ],
    ports: [
      {port: 27017},
    ],
  });
}

function redis(nodeName, name) {
  return deployment_service(name, {
    nodeName,
    containers: [
      {
        name,
        image: 'redis:latest@sha256:ae51486efeea8a9b3f85542e408f79a5012d5b7fa35ae19733104ecc6992a248',
        command: ['sh', '-c', 'rm -f /data/dump.rdb && redis-server --save \"\" --appendonly no'],
      },
    ],
    ports: [
      {port: 6379},
    ],
  });
}

function rabbitmq(nodeName, name, cookie) {
  return deployment_service(name, {
    nodeName,
    containers: [
      {
        name,
        image: 'rabbitmq:latest@sha256:d96c58d1e2e55a32a03fa9ba01d00c6383d1aca26fb2790f14ac411fd6e45152',
        env: env({
          RABBITMQ_ERLANG_COOKIE: cookie,
          RABBITMQ_DEFAULT_VHOST: '/',
        }),
      },
    ],
    ports: [
      {port: 5672},
    ],
  });
}

const doc1 = {
  apiVersion: 'v1',
  kind: 'List',
  items: [

    {
      apiVersion: 'v1',
      kind: 'Namespace',
      metadata: {
        name: 'social-network',
      },
    },

    ...deployment_service('jaeger', {
      nodeName: worker3,
      containers: [
        {
          name: 'jaeger',
          image: 'jaegertracing/all-in-one:latest@sha256:30238ffd383f266651cd4e0c36be67b6b0d3d882d0bbb67304c39af9ee61a4ef',
          env: env({
            COLLECTOR_ZIPKIN_HTTP_PORT: '9411',
          }),
        },
      ],
      serviceType: 'NodePort',
      ports: [
        {name: '16686', port: 16686, nodePort: 30005},
        {name: '9411', port: 9411},
      ],
    }),

    ...deployment_service('nginx-thrift', {
      nodeName: worker4,
      containers: [
        {
          name: 'nginx-thrift',
          image: image_nginx,
        },
        dnsmasq,
      ],
      serviceType: 'NodePort',
      ports: [
        {port: 8080, nodePort: 30001},
      ],
    }),

    ...cpp(worker3, 'compose-post-service', 'ComposePostService'),
    ...redis(worker3, 'compose-post-redis'),

    ...cpp(worker1, 'home-timeline-service', 'HomeTimelineService'),
    ...redis(worker3, 'home-timeline-redis'),

    ...cpp(worker3, 'media-service', 'MediaService'),

    ...cpp(worker2, 'post-storage-service', 'PostStorageService'),
    ...memcached(worker3, 'post-storage-memcached'),
    ...mongodb(worker3, 'post-storage-mongodb'),

    ...cpp(worker3, 'social-graph-service', 'SocialGraphService'),
    ...mongodb(worker3, 'social-graph-mongodb'),
    ...redis(worker3, 'social-graph-redis'),

    ...cpp(worker3, 'text-service', 'TextService'),

    ...cpp(worker3, 'unique-id-service', 'UniqueIdService'),

    ...cpp(worker3, 'url-shorten-service', 'UrlShortenService'),

    ...cpp(worker3, 'user-mention-service', 'UserMentionService'),

    ...cpp(worker3, 'user-service', 'UserService'),
    ...memcached(worker3, 'user-memcached'),
    ...mongodb(worker3, 'user-mongodb'),

    ...cpp(worker3, 'user-timeline-service', 'UserTimelineService'),
    ...mongodb(worker3, 'user-timeline-mongodb'),
    ...redis(worker3, 'user-timeline-redis'),

    ...rabbitmq(worker3, 'write-home-timeline-rabbitmq', 'WRITE-HOME-TIMELINE-RABBITMQ'),

    ...rabbitmq(worker3, 'write-user-timeline-rabbitmq', 'WRITE-USER-TIMELINE-RABBITMQ'),

    ...multi_deployment_service('media-filter-service', [worker1, worker2, worker3], {
      containers: [
        {
          name: 'media-filter-service',
          image: image_media_filter,
        },
      ],
      ports: [
        {port: 40000},
      ],
    }),

    ...deployment_service('text-filter-service', {
      nodeName: worker3,
      containers: [
        {
          name: 'text-filter-service',
          image: image_text_filter,
        },
      ],
      ports: [
        {port: 40000},
      ],
    }),

  ],
};

const doc2 = {
  apiVersion: 'v1',
  kind: 'List',
  items: [
    ...cpp(worker3, 'write-home-timeline-service', 'WriteHomeTimelineService'),
    ...cpp(worker3, 'write-user-timeline-service', 'WriteUserTimelineService'),
  ],
};

fs.writeFileSync('social-network/1.json', JSON.stringify(doc1, null, 2) + '\n');
fs.writeFileSync('social-network/2.json', JSON.stringify(doc2, null, 2) + '\n');
