import random
from locust import FastHttpUser, LoadTestShape, task, tag, between, events
import base64
import os
from pathlib import Path
import logging
import time
import json

import locust.stats
locust.stats.CONSOLE_STATS_INTERVAL_SEC = 600
locust.stats.HISTORY_STATS_INTERVAL_SEC = 60
locust.stats.CSV_STATS_INTERVAL_SEC = 60
locust.stats.CSV_STATS_FLUSH_INTERVAL_SEC = 60
locust.stats.CURRENT_RESPONSE_TIME_PERCENTILE_WINDOW = 60
locust.stats.PERCENTILES_TO_REPORT = [0.50, 0.80, 0.90, 0.95, 0.98, 0.99, 0.995, 0.999, 1.0]

random.seed(time.time())

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

image_dir  = Path('/root/social-network/src/wrk2/scripts/social-network/base64_images')
image_data = {}
image_names = []

logging.basicConfig(level=logging.INFO)

# data
for img in os.listdir(str(image_dir)):
    full_path = image_dir / img
    image_names.append(img)
    with open(str(full_path), 'r') as f:
        image_data[img] = f.read()

charset = ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', 'a', 's',
  'd', 'f', 'g', 'h', 'j', 'k', 'l', 'z', 'x', 'c', 'v', 'b', 'n', 'm', 'Q',
  'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', 'A', 'S', 'D', 'F', 'G', 'H',
  'J', 'K', 'L', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', '1', '2', '3', '4', '5',
  '6', '7', '8', '9', '0']

decset = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']

user_id_by_follower_num = {}
user_id_by_follower_num[10] = [3, 12, 14, 21, 24, 27, 29, 33, 37, 41, 42, 43,
    51, 58, 62, 69, 80, 84, 86, 92, 97, 117, 122, 123, 124, 133, 135, 159, 167,
    170, 181, 185, 187, 193, 195, 213, 215, 218, 219, 224, 253, 254, 263, 267, 271,
    272, 281, 289, 294, 297, 298, 300, 303, 306, 314, 316, 318, 342, 344, 346, 347,
    349, 350, 355, 358, 368, 372, 375, 378, 380, 392, 397, 401, 404, 414, 421, 425, 427,
    431, 442, 447, 449, 453, 459, 462, 477, 478, 479, 485, 486, 492, 503, 506, 507, 509,
    511, 513, 514, 520, 533, 546, 547, 548, 551, 553, 560, 564, 565, 573, 577, 588, 598,
    619, 621, 622, 623, 628, 641, 643, 653, 654, 657, 658, 661, 663, 665, 672, 675, 677,
    680, 684, 695, 696, 702, 707, 724, 727, 730, 732, 736, 745, 759, 764, 766, 768, 776,
    778, 779, 782, 783, 784, 787, 798, 800, 801, 803, 810, 814, 816, 817, 820, 827, 831,
    834, 835, 839, 840, 844, 850, 859, 862, 881, 885, 890, 891, 893, 897, 899, 902, 907,
    910, 911, 921, 925, 931, 932, 939, 942, 943, 961]
user_id_by_follower_num[30] = [4, 6, 8, 13, 15, 20, 22, 23, 26, 28, 31, 32, 36,
    38, 50, 53, 54, 55, 65, 66, 68, 70, 74, 76, 78, 79, 81, 83, 87, 89, 91, 93, 94,
    96, 100, 102, 106, 107, 108, 109, 111, 119, 120, 125, 129, 130, 137, 140, 142,
    144, 148, 151, 152, 153, 158, 165, 168, 169, 171, 173, 174, 175, 178, 180, 186,
    189, 190, 197, 200, 202, 205, 207, 209, 211, 212, 217, 221, 223, 225, 227, 228,
    233, 234, 235, 239, 240, 241, 242, 245, 247, 258, 262, 266, 269, 273, 274, 277,
    278, 279, 280, 282, 283, 286, 290, 292, 304, 305, 310, 319, 322, 323, 330, 331,
    333, 334, 335, 338, 341, 345, 352, 356, 357, 359, 360, 361, 363, 365, 367, 370,
    376, 383, 385, 386, 387, 389, 391, 394, 395, 402, 409, 412, 415, 417, 422, 428,
    433, 435, 437, 440, 445, 446, 448, 450, 454, 457, 463, 465, 469, 473, 481, 482,
    483, 484, 487, 490, 491, 497, 498, 499, 500, 504, 510, 512, 515, 519, 523, 524,
    527, 528, 535, 536, 537, 540, 541, 543, 544, 545, 549, 557, 559, 566, 567, 568,
    569, 570, 571, 581, 583, 584, 587, 590, 591, 593, 594, 596, 597, 599, 600, 605,
    608, 609, 611, 613, 614, 625, 626, 629, 630, 634, 635, 636, 638, 639, 642, 648,
    652, 660, 662, 664, 666, 668, 673, 674, 678, 683, 692, 693, 694, 698, 700, 705,
    708, 711, 714, 717, 721, 725, 726, 735, 741, 743, 749, 750, 755, 756, 762, 763,
    767, 771, 772, 780, 788, 789, 790, 799, 802, 804, 807, 809, 815, 818, 819, 822,
    823, 825, 826, 828, 829, 832, 836, 843, 848, 849, 855, 857, 858, 861, 865, 868,
    871, 872, 878, 882, 883, 887, 894, 896, 901, 903, 914, 917, 920, 922, 923, 929,
    944, 945, 946, 947, 949, 952, 956]
user_id_by_follower_num[50] = [2, 5, 7, 11, 16, 17, 18, 34, 35, 39, 40, 45, 46,
    47, 49, 56, 60, 63, 67, 71, 73, 82, 85, 90, 95, 104, 105, 110, 112, 113, 114,
    115, 116, 121, 126, 131, 138, 139, 141, 143, 156, 157, 164, 166, 176, 177, 179,
    182, 183, 191, 196, 199, 208, 220, 226, 237, 243, 244, 252, 257, 276, 285, 307,
    320, 324, 327, 332, 336, 340, 351, 354, 364, 371, 374, 377, 379, 381, 388, 390,
    393, 398, 406, 408, 411, 418, 423, 424, 426, 432, 434, 438, 439, 444, 451, 452,
    455, 464, 466, 467, 470, 471, 472, 475, 508, 516, 517, 518, 522, 530, 532, 534,
    539, 552, 554, 556, 578, 582, 589, 601, 603, 604, 607, 612, 615, 616, 620, 631,
    632, 647, 655, 659, 670, 676, 686, 687, 699, 703, 713, 715, 719, 720, 728, 731,
    734, 737, 739, 740, 751, 752, 753, 757, 761, 765, 769, 773, 777, 785, 786, 791,
    796, 821, 824, 841, 842, 845, 846, 851, 853, 854, 863, 867, 869, 874, 875, 876,
    880, 884, 898, 900, 904, 905, 915, 916, 919, 930, 934, 935, 948, 951, 955, 960,
    962]
user_id_by_follower_num[80] = [1, 9, 10, 25, 30, 44, 57, 59, 61, 72, 75, 77, 88,
    98, 99, 118, 127, 136, 150, 162, 172, 188, 192, 194, 198, 201, 210, 216, 231,
    248, 249, 251, 259, 284, 287, 288, 295, 296, 301, 308, 317, 325, 326, 337,
    339, 343, 348, 353, 362, 366, 369, 382, 384, 396, 399, 400, 407, 420, 429,
    430, 441, 443, 458, 460, 461, 468, 474, 476, 480, 488, 489, 493, 494, 502,
    521, 525, 531, 538, 542, 550, 561, 563, 572, 576, 585, 586, 595, 602, 606,
    610, 618, 624, 637, 640, 651, 667, 681, 682, 685, 688, 689, 690, 691, 697,
    701, 704, 706, 712, 722, 723, 729, 733, 738, 742, 744, 758, 770, 774, 775,
    794, 797, 811, 812, 813, 833, 838, 847, 852, 864, 877, 886, 906, 909, 912,
    913, 918, 924, 926, 927, 928, 933, 936, 937, 941, 950, 953, 954, 957, 959]
user_id_by_follower_num[100] = [19, 48, 64, 101, 128, 132, 134, 145, 146, 149,
    154, 161, 163, 184, 203, 232, 238, 250, 255, 256, 261, 264, 268, 291, 299,
    302, 312, 313, 329, 403, 405, 410, 416, 419, 436, 495, 496, 501, 505, 574,
    575, 579, 580, 627, 644, 645, 649, 650, 656, 671, 716, 754, 781, 792, 793,
    806, 860, 870, 879, 888, 895, 938, 940]
user_id_by_follower_num[300] = [52, 103, 147, 155, 160, 204, 206, 214, 222, 229,
    230, 236, 246, 260, 265, 270, 275, 293, 309, 311, 315, 321, 328, 373, 413,
    456, 526, 529, 555, 558, 562, 592, 617, 633, 646, 669, 679, 709, 710, 718,
    746, 747, 748, 760, 795, 805, 808, 830, 837, 856, 866, 873, 889, 892, 908, 958]

def random_string(length):
    global charset
    if length > 0:
        s = ""
        for i in range(0, length):
            s += random.choice(charset)
        return s
    else:
        return ""

def random_decimal(length):
    global decset
    if length > 0:
        s = ""
        for i in range(0, length):
            s += random.choice(decset)
        return s
    else:
        return ""

def compose_random_text():
    coin = random.random() * 100
    if coin <= 30.0:
        length = random.randint(0, 50)
    elif coin <= 58.2:
        length = random.randint(51, 100)
    elif coin <= 76.5:
        length = random.randint(101, 150)
    elif coin <= 85.3:
        length = random.randint(151, 200)
    elif coin <= 92.6:
        length = random.randint(201, 250)
    else:
        length = random.randint(251, 280)
    return random_string(length)

def compose_random_user():
    user = 0
    coin = random.random()*100
    if coin <= 0.4:
        user = random.choice(user_id_by_follower_num[10])
    elif coin <= 6.1:
        user = random.choice(user_id_by_follower_num[30])
    elif coin <= 16.6:
        user = random.choice(user_id_by_follower_num[50])
    elif coin <= 43.8:
        user = random.choice(user_id_by_follower_num[80])
    elif coin <= 66.8:
        user = random.choice(user_id_by_follower_num[100])
    else:
        user = random.choice(user_id_by_follower_num[300])
    return str(user)

mean_iat = 1  # seconds

request_log_file = open('request.log', 'a')

class SocialMediaUser(FastHttpUser):
    def wait_time(self):
        global intervals
        global mean_iat
        return random.expovariate(lambd=1/mean_iat)

    @events.request.add_listener
    def on_request(response_time, context, **kwargs):
        request_log_file.write(json.dumps({
            'time': time.perf_counter(),
            'latency': response_time / 1e3,
            'context': context,
        }) + '\n')

    @task(20)
    @tag('compose_post')
    def compose_post(self):
        global image_names
        global image_data
        #----------------- contents -------------------#
        user_id = compose_random_user()
        username = 'username_' + user_id
        text = compose_random_text()
        #---- user mentions ----#
        for i in range(0, 5):
            user_mention_id = random.randint(1, 2)
            while True:
                user_mention_id = random.randint(1, 962)
                if user_id != user_mention_id:
                    break
            text = text + " @username_" + str(user_mention_id)

        #---- urls ----#
        for i in range(0, 5):
            if random.random() <= 0.2:
                num_urls = random.randint(0, 5)
                for i in range(0, num_urls):
                    text = text + " https://www.bilibili.com/av" + random_decimal(8)

        #---- media ----#
        num_media = 0
        media_names = []
        medium = []
        media_types = []
        if random.random() < 0.25:
            num_media = random.randint(1, 4)
            # num_media = 1
        num_media = 1
        for i in range(0, num_media):
            img_name = random.choice(image_names)
            if 'jpg' in img_name:
                media_types.append('jpg')
            elif 'png' in img_name:
                media_types.append('png')
            else:
                continue
            medium.append(image_data[img_name])
            media_names.append(img_name)
        media_names = ' '.join(media_names)

        params = {}

        url = '/wrk2-api/post/compose'
        img = random.choice(image_names)
        body = {}
        if num_media > 0:
            body['username'] = username
            body['user_id'] = user_id
            body['text'] = text
            body['medium'] = json.dumps(medium)
            body['media_types'] = json.dumps(media_types)
            body['post_type'] = '0'
        else:
            body['username'] = username
            body['user_id'] = user_id
            body['text'] = text
            body['medium'] = ''
            body['media_types'] = ''
            body['post_type'] = '0'

        r = self.client.post(url, params=params,
            data=body, name='compose_post',
            context={'type': 'compose_post', 'num_media': num_media, 'text': text, 'media_names': media_names})

        if r.status_code > 202:
            logging.warning('compose_post resp.status = %d, text=%s' %(r.status_code,
                r.text))


    @task(65)
    @tag('read_home_timeline')
    def read_home_timeline(self):
        start = random.randint(0, 100)
        stop  = start + 10

        url = '/wrk2-api/home-timeline/read'
        args = {}
        args['user_id'] = str(random.randint(1, 962))
        args['start'] = str(start)
        args['stop'] = str(stop)

        r = self.client.get(url, params=args, name='read_home_line',
            context={'type': 'read_home_timeline', 'start': start, 'user_id': args['user_id']})

        if r.status_code > 202:
            logging.warning('read_home_timeline resp.status = %d, text=%s' %(r.status_code,
                r.text))

    @task(15)
    @tag('read_user_timeline')
    def read_user_timeline(self):
        start = random.randint(0, 100)
        stop  = start + 10

        url = '/wrk2-api/user-timeline/read'
        args = {}
        args['user_id'] = str(random.randint(1, 962))
        args['start'] = str(start)
        args['stop'] = str(stop)

        r = self.client.get(url, params=args, name='read_user_timeline',
            context={'type': 'read_user_timeline', 'start': start, 'user_id': args['user_id']})

        if r.status_code > 202:
            logging.warning('read_user_timeline resp.status = %d, text=%s' %(r.status_code,
                r.text))


RPS = list(map(int, Path('rps.txt').read_text().splitlines()))


class CustomShape(LoadTestShape):
    time_limit = len(RPS)
    spawn_rate = 100

    def tick(self):
        run_time = self.get_run_time()
        if run_time < self.time_limit:
            user_count = RPS[int(run_time)]
            return (user_count, self.spawn_rate)
        return None
