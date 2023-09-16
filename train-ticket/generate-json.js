#!/usr/bin/env node
'use strict';

const fs = require('fs');

const worker1 = 'autothrottle-2';
const worker2 = 'autothrottle-3';
const worker3 = 'autothrottle-4';
const worker4 = 'autothrottle-5';
const namespace = 'train-ticket';

function labels(name) {
  return {
    app: name,
  };
}

function deployment(nodeName, name, { containers }) {
  return {
    "apiVersion": "apps/v1",
    "kind": "Deployment",
    "metadata": {
      namespace,
      name,
    },
    "spec": {
      "selector": {
        "matchLabels": labels(name),
      },
      replicas: 1,
      "template": {
        "metadata": {
          "labels": labels(name),
        },
        "spec": {
          nodeName,
          containers,
          restartPolicy: 'Always',
          enableServiceLinks: false,
        }
      }
    }
  };
}

function service(name, ports, { serviceType }={}) {
  return {
    "apiVersion": "v1",
    "kind": "Service",
    "metadata": {
      namespace,
      name,
    },
    "spec": {
      type: serviceType,
      ports,
      "selector": labels(name),
    }
  };
}

function java(nodeName, name, port, { extraEnv=[], noCommand=false }={}) {
  const image = {
    'ts-admin-basic-info-service': 'codewisdom/ts-admin-basic-info-service:0.2.1@sha256:601f3095bd8da5a4f3ab7e29f14afcbef00187682db976772f975810cbce8004',
    'ts-admin-order-service': 'codewisdom/ts-admin-order-service:0.2.1@sha256:3459fa7f1bc0b4724c1496e8ba8fec60181b6559dec0168b87da3b5bedfe8a0d',
    'ts-admin-route-service': 'codewisdom/ts-admin-route-service:0.2.1@sha256:c6fe3cfb82817d972b5c32fae2a14b99e4d9e52b8790367db03659b4c6a58b43',
    'ts-admin-travel-service': 'codewisdom/ts-admin-travel-service:0.2.1@sha256:617c3f709b8e0089d22f62a0fc37d8eaf7a2a8d83027a3193202224c8dc076eb',
    'ts-admin-user-service': 'codewisdom/ts-admin-user-service:0.2.1@sha256:fa4cc3a5d72138688d15421b6d8e42fb86e143ae3e45de2025895aa0c2af1801',
    'ts-assurance-service': 'codewisdom/ts-assurance-service:0.2.1@sha256:3b5f1c735b2c79cc8179f2339a19e02806f777e65e83e2e023c922a72337af3c',
    'ts-auth-service': 'codewisdom/ts-auth-service:0.2.1@sha256:d635f47365721ae8ed37206f246cb96f935d4f54da9474d871ca13c25c41c231',
    'ts-basic-service': 'codewisdom/ts-basic-service:0.2.1@sha256:93598bd07e0c703788f67cda122394620410bb140e44e6a2422e6bec84145c4e',
    'ts-cancel-service': 'codewisdom/ts-cancel-service:0.2.1@sha256:0812ed7c3281bf75eba703ccbd79abb6587e3ca38507b74f37527ce8ad12f427',
    'ts-config-service': 'codewisdom/ts-config-service:0.2.1@sha256:a94813d69464525be2fb86a535f5b1799225a936921c214f18b95acb99985466',
    'ts-consign-price-service': 'codewisdom/ts-consign-price-service:0.2.1@sha256:90c740e21fc77d657a20c13a3a1a4d518d6a4ca0c121a6184475938bdc272c3b',
    'ts-consign-service': 'codewisdom/ts-consign-service:0.2.1@sha256:8fe341338a7b4d244ec12e5b35c90bee2eec8c1c901896e5037b78ce3505c882',
    'ts-contacts-service': 'codewisdom/ts-contacts-service:0.2.1@sha256:725be6a0bda6674f1a71d30e658dbaef772c7fb384164a36c4489845e7738657',
    'ts-delivery-service': 'codewisdom/ts-delivery-service:0.2.1@sha256:fa9fd1cbe73207a07c2ac6cf268d288545692a9a64430a0b4e1a5127908802cf',
    'ts-execute-service': 'codewisdom/ts-execute-service:0.2.1@sha256:637f66e0338682807ee7e77d773540c33f0b2f8d0143178687028b660f7348c7',
    'ts-food-map-service': 'codewisdom/ts-food-map-service:0.2.1@sha256:6ad2077df52547f1ef3b0fbafc77c202ae7d140d59bde00d494e3a1ae2090c36',
    'ts-food-service': 'codewisdom/ts-food-service:0.2.1@sha256:07ff7ddc36fc5dbd0371569df7517d699674e7ffa51594c12518428749f9c669',
    'ts-inside-payment-service': 'codewisdom/ts-inside-payment-service:0.2.1@sha256:4df0f48b6110f151b76150624d1b9ed57250e28dafc6b5309c1b089261123390',
    'ts-news-service': 'codewisdom/ts-news-service:0.2.1@sha256:0f8ae8b5f09239f14f8b50ac02e3bc08e2f05fb011c48e65c174aaa3dd6c5326',
    'ts-notification-service': 'codewisdom/ts-notification-service:0.2.1@sha256:e6cecc7fa562d6b3f61d1bfc7f1319d27394406b5b262235e032292979d8cef4',
    'ts-order-other-service': 'codewisdom/ts-order-other-service:0.2.1@sha256:9fb33c018ae66eb308432bd2409254ad733f93d850498a0076e9e311a87e5f56',
    'ts-order-service': 'codewisdom/ts-order-service:0.2.1@sha256:85d9dccfeed752462feab73877174daa8a0436ddabc6fbb65cecb608e69a4f9c',
    'ts-payment-service': 'codewisdom/ts-payment-service:0.2.1@sha256:7e315dc43ddca64d38274bb4bcc04baaf3cb14cfbe4b83c85bd7ae604e047f14',
    'ts-preserve-other-service': 'codewisdom/ts-preserve-other-service:0.2.1@sha256:0db786c18d96df72f7c40a32c5a62e8d126392296ad9f0a3ba9e3edd79226ef8',
    'ts-preserve-service': 'codewisdom/ts-preserve-service:0.2.1@sha256:bb1b7f1e9caddf9ae819f365e4329c26fb042e89a7d61eff0dd31c54eafd12eb',
    'ts-price-service': 'codewisdom/ts-price-service:0.2.1@sha256:06778da3b5c9d4af5de7320cabced0b2ac5e9f3981de3f20a32c9686add2d27e',
    'ts-rebook-service': 'codewisdom/ts-rebook-service:0.2.1@sha256:8115f0ddefd912289a8c058fd969ae0f42d514d5a53ef8c6b0bed60dbd2d6362',
    'ts-route-plan-service': 'codewisdom/ts-route-plan-service:0.2.1@sha256:c384d943f1a670570252e706e0770b09f0f716574e81d7ec6b54788eff025507',
    'ts-route-service': 'codewisdom/ts-route-service:0.2.1@sha256:825c997b808254de467755efcec0fd3140a0769bf385fcef81f7ad625a8189ff',
    'ts-seat-service': 'codewisdom/ts-seat-service:0.2.1@sha256:c28cee5df11120633f790e7e34282a3cd4dd3a43f1edbb68f86d32cdc9a92389',
    'ts-security-service': 'codewisdom/ts-security-service:0.2.1@sha256:eecaa520cf3a33a9ffce66688777ff61549931b8013c3dcae901544c41563432',
    'ts-station-service': 'codewisdom/ts-station-service:0.2.1@sha256:ae1f66358a59ba1eea9079498e08b6a1fa8713ab3fd2760c500d21254d2985b0',
    'ts-ticketinfo-service': 'codewisdom/ts-ticketinfo-service:0.2.1@sha256:b01122cfbf386cde4cb006989534b7edbb0fc2a5873b607f3d1b5d3b8de45427',
    'ts-ticket-office-service': 'codewisdom/ts-ticket-office-service:0.2.1@sha256:6d6f01686c4001b33d168fdf0a0a45c2851e46c11f0064e1e563a366d662b334',
    'ts-train-service': 'codewisdom/ts-train-service:0.2.1@sha256:c2321c822bc7d6d6afb5bda65105f6222611621e196f0b752aa0152b80373124',
    'ts-travel2-service': 'codewisdom/ts-travel2-service:0.2.1@sha256:48b33c1309c6a7b576b38ab6bbeb0ff89cf98473270593df14ea56709f3c3601',
    'ts-travel-plan-service': 'codewisdom/ts-travel-plan-service:0.2.1@sha256:c9bd904a84cea8fc1e479eb83ba5d79edcc979277ea13658b8bf48d9a8f7ac68',
    'ts-travel-service': 'codewisdom/ts-travel-service:0.2.1@sha256:0c8a669cfc68be7149a05856f1c60201a0a6db6612b3f81f370caae452f85a82',
    'ts-user-service': 'codewisdom/ts-user-service:0.2.1@sha256:0b240607b7bec3dd9b7e4f4b4c0361d9281a25648ccb36c427330f9cf918e407',
    'ts-verification-code-service': 'codewisdom/ts-verification-code-service:0.2.1@sha256:8fba43bf35a60ac3bbebcec8914f1b1de990ad0a5c21e18d35860e9b336e6922',
    'ts-voucher-service': 'codewisdom/ts-voucher-service:0.2.1@sha256:2635aefb54f22f32faff08fa4bb702593ec8e4b8e9760ed835df507d53242457',
  }[name];
  return deployment(nodeName, name, {
    containers: [
      {
        name,
        image,
        "imagePullPolicy": "IfNotPresent",
        "command": noCommand ? undefined : [
          "java",
          "-jar",
          `/app/${name}-1.0.jar`,
        ],
        "env": [
          {
            "name": "NODE_IP",
            "valueFrom": {
              "fieldRef": {
                "fieldPath": "status.hostIP"
              }
            }
          },
          ...extraEnv,
        ],
        "ports": [
          {
            "containerPort": port,
          }
        ],
        "readinessProbe": {
          "tcpSocket": {
            port,
          },
          "initialDelaySeconds": 60,
          "periodSeconds": 10,
          "timeoutSeconds": 5
        }
      }
    ],
  });
}

function mongodb(nodeName, name) {
  return deployment(nodeName, name, {
    containers: [
      {
        name,
        "image": 'mongo:5.0.2-focal@sha256:3938ddf3039cc291ce26ef63fddfb36441f8fae9909a5e5ec521453d850de812',
        "imagePullPolicy": "IfNotPresent",
        "ports": [
          {
            "containerPort": 27017
          }
        ],
      }
    ],
  });
}

const rabbitmqEnv = [
  {
    "name": "rabbitmq_host",
    "value": "rabbitmq"
  },
  {
    "name": "rabbitmq_port",
    "value": "5672"
  },
];

const doc = {
  apiVersion: 'v1',
  kind: 'List',
  items: [
    {
      apiVersion: 'v1',
      kind: 'Namespace',
      metadata: {
        name: namespace,
      },
    },
    mongodb(worker2, 'ts-user-mongo'),
    mongodb(worker2, 'ts-auth-mongo'),
    mongodb(worker4, 'ts-route-mongo'),
    mongodb(worker3, 'ts-contacts-mongo'),
    mongodb(worker1, 'ts-order-mongo'),
    mongodb(worker3, 'ts-order-other-mongo'),
    mongodb(worker2, 'ts-config-mongo'),
    mongodb(worker3, 'ts-station-mongo'),
    mongodb(worker4, 'ts-train-mongo'),
    mongodb(worker1, 'ts-travel-mongo'),
    mongodb(worker1, 'ts-travel2-mongo'),
    mongodb(worker4, 'ts-price-mongo'),
    mongodb(worker3, 'ts-security-mongo'),
    mongodb(worker2, 'ts-inside-payment-mongo'),
    mongodb(worker2, 'ts-payment-mongo'),
    mongodb(worker3, 'ts-assurance-mongo'),
    mongodb(worker3, 'ts-ticket-office-mongo'),
    deployment(worker3, 'ts-voucher-mysql', {
      containers: [
        {
          name: 'ts-voucher-mysql',
          "image": "mysql:5.6.35@sha256:c2f3286842500ac9e4f81b638f6c488314d7a81784bc7fd1ba806816d70abb55",
          "imagePullPolicy": "IfNotPresent",
          "env": [
            {
              "name": "MYSQL_ROOT_PASSWORD",
              "value": "root"
            }
          ],
          "ports": [
            {
              "containerPort": 3306
            }
          ],
        }
      ],
    }),
    mongodb(worker3, 'ts-food-map-mongo'),
    mongodb(worker3, 'ts-consign-mongo'),
    mongodb(worker3, 'ts-consign-price-mongo'),
    mongodb(worker3, 'ts-food-mongo'),
    mongodb(worker3, 'ts-notification-mongo'),
    service('ts-notification-mongo', [{ port: 27017 }]),
    mongodb(worker3, 'ts-delivery-mongo'),
    service('ts-delivery-mongo', [{ port: 27017 }]),
    deployment(worker3, 'rabbitmq', {
      containers: [
        {
          "name": "rabbitmq",
          "image": "rabbitmq:3@sha256:50282e8cbf22ac261efd13fb881da900c09367ceb166c3ec5d23089986464df6",
          "imagePullPolicy": "IfNotPresent",
          "ports": [
            {
              "containerPort": 5672
            }
          ],
        }
      ],
    }),
    service('rabbitmq', [{ port: 5672 }]),
    service('ts-user-mongo', [{ port: 27017 }]),
    service('ts-auth-mongo', [{ port: 27017 }]),
    service('ts-route-mongo', [{ port: 27017 }]),
    service('ts-contacts-mongo', [{ port: 27017 }]),
    service('ts-order-mongo', [{ port: 27017 }]),
    service('ts-order-other-mongo', [{ port: 27017 }]),
    service('ts-config-mongo', [{ port: 27017 }]),
    service('ts-station-mongo', [{ port: 27017 }]),
    service('ts-train-mongo', [{ port: 27017 }]),
    service('ts-travel-mongo', [{ port: 27017 }]),
    service('ts-travel2-mongo', [{ port: 27017 }]),
    service('ts-price-mongo', [{ port: 27017 }]),
    service('ts-security-mongo', [{ port: 27017 }]),
    service('ts-inside-payment-mongo', [{ port: 27017 }]),
    service('ts-payment-mongo', [{ port: 27017 }]),
    service('ts-assurance-mongo', [{ port: 27017 }]),
    service('ts-ticket-office-mongo', [{ port: 27017 }]),
    service('ts-voucher-mysql', [{ port: 3306 }]),
    service('ts-food-map-mongo', [{ port: 27017 }]),
    service('ts-consign-mongo', [{ port: 27017 }]),
    service('ts-consign-price-mongo', [{ port: 27017 }]),
    service('ts-food-mongo', [{ port: 27017 }]),
    java(worker4, 'ts-admin-basic-info-service', 18767),
    java(worker3, 'ts-admin-order-service', 16112),
    java(worker4, 'ts-admin-route-service', 16113),
    java(worker1, 'ts-admin-travel-service', 16114),
    java(worker2, 'ts-admin-user-service', 16115),
    java(worker3, 'ts-assurance-service', 18888),
    java(worker4, 'ts-basic-service', 15680),
    java(worker3, 'ts-cancel-service', 18885),
    java(worker2, 'ts-config-service', 15679), //XXX
    java(worker3, 'ts-consign-price-service', 16110),
    java(worker3, 'ts-consign-service', 16111),
    java(worker3, 'ts-contacts-service', 12347),
    java(worker3, 'ts-execute-service', 12386),
    java(worker3, 'ts-food-map-service', 18855),
    java(worker3, 'ts-food-service', 18856, { extraEnv: rabbitmqEnv }),
    java(worker2, 'ts-inside-payment-service', 18673), //XXX
    java(worker2, 'ts-auth-service', 12340), //XXX
    java(worker1, 'ts-news-service', 12862, { noCommand: true }),
    java(worker3, 'ts-notification-service', 17853, { extraEnv: rabbitmqEnv }),
    java(worker3, 'ts-order-other-service', 12032),
    java(worker1, 'ts-order-service', 12031),
    java(worker2, 'ts-payment-service', 19001), //XXX
    java(worker3, 'ts-preserve-other-service', 14569, { extraEnv: rabbitmqEnv }),
    java(worker3, 'ts-preserve-service', 14568, { extraEnv: rabbitmqEnv }),
    java(worker4, 'ts-price-service', 16579),
    java(worker2, 'ts-rebook-service', 18886),
    java(worker3, 'ts-route-plan-service', 14578),
    java(worker4, 'ts-route-service', 11178),
    java(worker1, 'ts-seat-service', 18898),
    java(worker3, 'ts-security-service', 11188),
    java(worker2, 'ts-user-service', 12342), //XXX
    java(worker3, 'ts-station-service', 12345),
    java(worker3, 'ts-ticket-office-service', 16108, { noCommand: true }),
    java(worker2, 'ts-ticketinfo-service', 15681),
    java(worker4, 'ts-train-service', 14567),
    java(worker1, 'ts-travel2-service', 16346),
    java(worker3, 'ts-travel-plan-service', 14322),
    java(worker1, 'ts-travel-service', 12346),
    java(worker3, 'ts-delivery-service', 18808, { extraEnv: rabbitmqEnv }),
    java(worker2, 'ts-verification-code-service', 15678),
    java(worker3, 'ts-voucher-service', 16101, { noCommand: true }),
    service('ts-admin-basic-info-service', [{ name: 'http', port: 18767 }]),
    service('ts-delivery-service', [{ name: 'http', port: 18808 }]),
    service('ts-admin-order-service', [{ name: 'http', port: 16112 }]),
    service('ts-admin-route-service', [{ name: 'http', port: 16113 }]),
    service('ts-admin-travel-service', [{ name: 'http', port: 16114 }]),
    service('ts-admin-user-service', [{ name: 'http', port: 16115 }]),
    service('ts-assurance-service', [{ name: 'http', port: 18888 }]),
    service('ts-basic-service', [{ name: 'http', port: 15680 }]),
    service('ts-cancel-service', [{ name: 'http', port: 18885 }]),
    service('ts-config-service', [{ name: 'http', port: 15679 }]),
    service('ts-consign-price-service', [{ name: 'http', port: 16110 }]),
    service('ts-consign-service', [{ name: 'http', port: 16111 }]),
    service('ts-contacts-service', [{ name: 'http', port: 12347 }]),
    service('ts-execute-service', [{ name: 'http', port: 12386 }]),
    service('ts-food-map-service', [{ name: 'http', port: 18855 }]),
    service('ts-food-service', [{ name: 'http', port: 18856 }]),
    service('ts-inside-payment-service', [{ name: 'http', port: 18673 }]),
    service('ts-user-service', [{ name: 'http', port: 12342 }]),
    service('ts-notification-service', [{ name: 'http', port: 17853 }]),
    service('ts-news-service', [{ name: 'http', port: 12862 }]),
    service('ts-order-other-service', [{ name: 'http', port: 12032 }]),
    service('ts-order-service', [{ name: 'http', port: 12031 }]),
    service('ts-payment-service', [{ name: 'http', port: 19001 }]),
    service('ts-preserve-other-service', [{ name: 'http', port: 14569 }]),
    service('ts-preserve-service', [{ name: 'http', port: 14568 }]),
    service('ts-price-service', [{ name: 'http', port: 16579 }]),
    service('ts-rebook-service', [{ name: 'http', port: 18886 }]),
    service('ts-route-plan-service', [{ name: 'http', port: 14578 }]),
    service('ts-route-service', [{ name: 'http', port: 11178 }]),
    service('ts-seat-service', [{ name: 'http', port: 18898 }]),
    service('ts-security-service', [{ name: 'http', port: 11188 }]),
    service('ts-auth-service', [{ name: 'http', port: 12340, nodePort: 30000 }], { serviceType: 'NodePort' }),
    service('ts-station-service', [{ name: 'http', port: 12345 }]),
    service('ts-ticket-office-service', [{ name: 'http', port: 16108 }]),
    service('ts-ticketinfo-service', [{ name: 'http', port: 15681 }]),
    service('ts-train-service', [{ name: 'http', port: 14567 }]),
    service('ts-travel2-service', [{ name: 'http', port: 16346 }]),
    service('ts-travel-plan-service', [{ name: 'http', port: 14322 }]),
    service('ts-travel-service', [{ name: 'http', port: 12346 }]),
    service('ts-verification-code-service', [{ name: 'http', port: 15678 }]),
    service('ts-voucher-service', [{ name: 'http', port: 16101 }]),
    deployment(worker2, 'ts-avatar-service', {
      containers: [
        {
          "name": "ts-avatar-service",
          "image": "codewisdom/ts-avatar-service:0.2.1@sha256:ab1ecb1a3165c625981aae045801107e45a5b6be2d6088de534ed5bba8aae2f5",
          "imagePullPolicy": "IfNotPresent",
          "ports": [
            {
              "containerPort": 17001
            }
          ],
          "readinessProbe": {
            "tcpSocket": {
              "port": 17001
            },
            "initialDelaySeconds": 160,
            "periodSeconds": 10,
            "timeoutSeconds": 5
          }
        },
      ],
    }),
    service('ts-avatar-service', [{ name: 'http', port: 17001 }]),
    deployment(worker3, 'ts-ui-dashboard', {
      containers: [
        {
          "name": "ts-ui-dashboard",
          "image": "codewisdom/ts-ui-dashboard:0.2.1@sha256:d98b6bf0c99d2d7467d322740e9e54bf322c8f77ca3077d80c295ebd6619e338",
          "imagePullPolicy": "IfNotPresent",
          "ports": [
            {
              "containerPort": 8080
            }
          ],
        },
      ],
    }),
    service('ts-ui-dashboard', [{ name: 'http', port: 8080, nodePort: 30001 }], { serviceType: 'NodePort' }),
  ],
};

fs.writeFileSync('train-ticket/1.json', JSON.stringify(doc, null, 2) + '\n');
