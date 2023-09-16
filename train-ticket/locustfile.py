from locust import HttpUser, LoadTestShape, task, between, events
from requests.adapters import HTTPAdapter
from datetime import datetime, timedelta, date
from pathlib import Path
import random
import time
import logging
import uuid
import json
import locust.stats
import time
import requests

locust.stats.CONSOLE_STATS_INTERVAL_SEC = 600
locust.stats.HISTORY_STATS_INTERVAL_SEC = 60
locust.stats.CSV_STATS_INTERVAL_SEC = 60
locust.stats.CSV_STATS_FLUSH_INTERVAL_SEC = 60
locust.stats.CURRENT_RESPONSE_TIME_PERCENTILE_WINDOW = 60
locust.stats.PERCENTILES_TO_REPORT = [0.50, 0.80, 0.90, 0.95, 0.98, 0.99, 0.995, 0.999, 1.0]

LOG_STATISTICS_IN_HALF_MINUTE_CHUNKS = (1==0)
RETRY_ON_ERROR = True
MAX_RETRIES = 10

STATUS_BOOKED = 0
STATUS_PAID = 1
STATUS_COLLECTED = 2
STATUS_CANCELLED = 4
STATUS_EXECUTED = 6

RPS = list(map(int, Path('rps.txt').read_text().splitlines()))
NUM_USERS = 1
USER_POOL = []
INTERVAL = 1

request_log_file = open('request.log', 'a')


spawning_complete = False
@events.spawning_complete.add_listener
def on_spawning_complete(user_count, **kwargs):
    global spawning_complete
    spawning_complete = True

@events.request.add_listener
def on_request(context, **kwargs):
    time.sleep(random.expovariate(lambd=1/INTERVAL))

def get_json_from_response(response):
    response_as_text = response.content.decode('UTF-8')
    response_as_json = json.loads(response_as_text)
    return response_as_json

def try_until_success(f):
    for attempt in range(MAX_RETRIES):
        #logging.warning(f"### DEBUG try_until_success: Calling function {f.__name__}, attempt {attempt}...")

        try:
            result, status = f()
            result_as_string = str(result)
            #logging.warning(f"### DEBUG try_until_success: Result of calling function {f.__name__} was: {result_as_string}.")
            if status == 1:
                return result
            else:
                logging.warning(f"### DEBUG try_until_success: Failed calling function {f.__name__}, response was {result_as_string}, trying again:")
                time.sleep(1)
        except Exception as e:
            exception_as_text = str(e)
            logging.warning(f"### DEBUG try_until_success: Failed calling function {f.__name__}, exception was: {exception_as_text}, trying again.")
            time.sleep(1)

        if not RETRY_ON_ERROR:
            break

    raise Exception("Weird... Cannot call endpoint.")

def create_users(host):
    session = requests.Session()

    def api_call_admin_login():
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        body = {"username": "admin", "password": "222222"}
        response = session.post(url=host+"/api/v1/users/login", headers=headers, json=body)
        response_as_json = get_json_from_response(response)
        return response_as_json, response_as_json["status"]

    response_as_json = try_until_success(api_call_admin_login)
    data = response_as_json["data"]
    token = data["token"]

    for _ in range(NUM_USERS):
        username = str(uuid.uuid4())
        password = "12345678"

        def api_call_admin_create_user():
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
            body = {"documentNum": None, "documentType": 0, "email": "string", "gender": 0, "password": password, "userName": username}
            response = session.post(url=host+"/api/v1/adminuserservice/users", headers=headers, json=body)
            response_as_json = get_json_from_response(response)
            return response_as_json, response_as_json["status"]

        response_as_json = try_until_success(api_call_admin_create_user)
        data = response_as_json["data"]
        user_id = data["userId"]

        def api_call_create_contact_for_user():
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
            body = {"accountId": user_id, "name": username, "documentType": "1", "documentNumber": "123456", "phoneNumber": "123456"}
            response = session.post(url=host+"/api/v1/contactservice/contacts/admin", headers=headers, json=body)
            response_as_json = get_json_from_response(response)
            return response_as_json, response_as_json["status"]

        try_until_success(api_call_create_contact_for_user)
        USER_POOL.append((username, password))

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    create_users('http://localhost:30001')

def login(client, username, password):
    def api_call_login():
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        body = {"username": username, "password": password}
        response = client.post(url="/api/v1/users/login", headers=headers, json=body, name=get_name_suffix("login"), timeout=10,
            context={'type': 'login'})
        response_as_json = get_json_from_response(response)
        return response_as_json, response_as_json["status"]

    response_as_json = try_until_success(api_call_login)
    data = response_as_json["data"]
    user_id = data["userId"]
    token = data["token"]

    return user_id, token

def next_weekday(d, weekday):
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0: # Target day already happened this week
        days_ahead += 7
    return d + timedelta(days_ahead)

def get_name_suffix(name):
    # global spawning_complete
    # if not spawning_complete:
    #     name = name + "_spawning"

    if LOG_STATISTICS_IN_HALF_MINUTE_CHUNKS:
        now = datetime.now()
        now = datetime(now.year, now.month, now.day, now.hour, now.minute, 0 if now.second < 30 else 30, 0)
        now_as_timestamp = int(now.timestamp())
        return f"{name}@{now_as_timestamp}"
    else:
        return name

def home(client):
    client.get("/index.html", name=get_name_suffix("home"),
        context={'type': 'home'})

def get_departure_date():
    # We always start next Monday because there a train from Shang Hai to Su Zhou starts.
    departure_date  = datetime.now() + timedelta(random.randint(1, 150))
    departure_date = departure_date.strftime("%Y-%m-%d")
    return departure_date

def get_trip_information(client, from_station, to_station):
    departure_date = get_departure_date()

    def api_call_get_trip_information():
        body = {"startingPlace": from_station, "endPlace": to_station, "departureTime": departure_date}
        response = client.post(url="/api/v1/travelservice/trips/left", json=body, name=get_name_suffix("get_trip_information"), timeout=10,
            context={'type': 'get_trip_information'})
        response_as_json = get_json_from_response(response)
        return response_as_json, response_as_json["status"]

    try_until_success(api_call_get_trip_information)

def search_departure(client):
    get_trip_information(client, "Shang Hai", "Su Zhou")

def search_return(client):
    get_trip_information(client, "Su Zhou", "Shang Hai")

def book(client, user_id, username):
    # we always start next Monday
    departure_date = datetime.now() + timedelta(random.randint(1, 150))
    departure_date = departure_date.strftime("%Y-%m-%d")

    def api_call_insurance():
        response = client.get(url="/api/v1/assuranceservice/assurances/types", name=get_name_suffix("get_assurance_types"),
            context={'type': 'insurance'})
        response_as_json = get_json_from_response(response)
        return response_as_json, response_as_json["status"]

    def api_call_food():
        response = client.get(url=f"/api/v1/foodservice/foods/{departure_date}/Shang%20Hai/Su%20Zhou/D1345", name=get_name_suffix("get_food_types"),
            context={'type': 'food'})
        response_as_json = get_json_from_response(response)
        return response_as_json, response_as_json["status"]

    def api_call_contacts():
        response = client.get(url=f"/api/v1/contactservice/contacts/account/{user_id}", name=get_name_suffix("query_contacts"),
            context={'type': 'contacts'})
        response_as_json = get_json_from_response(response)
        return response_as_json, response_as_json["status"]

    try_until_success(api_call_insurance)
    try_until_success(api_call_food)
    response_as_json = try_until_success(api_call_contacts)
    data = response_as_json["data"]
    contact_id = data[0]["id"]

    def api_call_ticket():
        body = {"accountId": user_id, "contactsId": contact_id, "tripId": "D1345", "seatType": "2", "date": departure_date, "from": "Shang Hai", "to": "Su Zhou", "assurance": "0", "foodType": 1, "foodName": "Bone Soup", "foodPrice": 2.5, "stationName": "", "storeName": ""}
        response = client.post(url="/api/v1/preserveservice/preserve", json=body, name=get_name_suffix("preserve_ticket"), timeout=10,
            context={'type': 'ticket'})
        response_as_json = get_json_from_response(response)
        return response_as_json, response_as_json["status"]

    try_until_success(api_call_ticket)

def get_last_order(client, user_id, expected_status):
    def api_call_query():
        body = {"loginId": user_id, "enableStateQuery": "false", "enableTravelDateQuery": "false", "enableBoughtDateQuery": "false", "travelDateStart": "null", "travelDateEnd": "null", "boughtDateStart": "null", "boughtDateEnd": "null"}
        response = client.post(url="/api/v1/orderservice/order/refresh", json=body, name=get_name_suffix("get_order_information"), timeout=10,
            context={'type': 'get_last_order'})
        response_as_json = get_json_from_response(response)
        return response_as_json, response_as_json["status"]

    response_as_json = try_until_success(api_call_query)
    data = response_as_json["data"]

    order_id = None
    for entry in data:
        if entry["status"]==expected_status:
            return entry

    return None

def get_last_order_id(client, user_id, expected_status):
    order = get_last_order(client, user_id, expected_status)

    if order!=None:
        order_id = order["id"]
        return order_id

    return None

def pay(client, user_id):
    order_id = get_last_order_id(client, user_id, STATUS_BOOKED)
    if order_id == None:
        raise Exception("Weird... There is no order to pay.")

    def api_call_pay():
        body = {"orderId": order_id, "tripId": "D1345"}
        response = client.post(url="/api/v1/inside_pay_service/inside_payment", json=body, name=get_name_suffix("pay_order"), timeout=10,
            context={'type': 'pay'})
        response_as_json = get_json_from_response(response)
        return response_as_json, response_as_json["status"]

    try_until_success(api_call_pay)

def cancel(client, user_id):
    order_id = get_last_order_id(client, user_id, STATUS_BOOKED)
    if order_id == None:
        raise Exception("Weird... There is no order to cancel.")

    def api_call_cancel():
        response = client.get(url=f"/api/v1/cancelservice/cancel/{order_id}/{user_id}", name=get_name_suffix("cancel_order"),
            context={'type': 'cancel'})
        response_as_json = get_json_from_response(response)
        return response_as_json, response_as_json["status"]

    try_until_success(api_call_cancel)

def consign(client, user_id):
    departure_date = get_departure_date()
    order_id = get_last_order_id(client, user_id, STATUS_BOOKED)
    if order_id == None:
        raise Exception("Weird... There is no order to consign.")

    def api_call_consign():
        body={"accountId": user_id, "handleDate": departure_date, "from": "Shang Hai", "to": "Su Zhou", "orderId": order_id, "consignee": order_id, "phone": "123", "weight": "1", "id": "", "isWithin": "false"}
        response = client.put(url="/api/v1/consignservice/consigns", json=body, name=get_name_suffix("create_consign"),
            context={'type': 'consign'})
        response_as_json = get_json_from_response(response)
        return response_as_json, response_as_json["status"]

    try_until_success(api_call_consign)

def collect_and_use(client, user_id):
    order_id = get_last_order_id(client, user_id, STATUS_PAID)
    if order_id == None:
        raise Exception("Weird... There is no order to collect.")

    def api_call_collect_ticket():
        response = client.get(url=f"/api/v1/executeservice/execute/collected/{order_id}", name=get_name_suffix("collect_ticket"),
            context={'type': 'collect'})
        response_as_json = get_json_from_response(response)
        return response_as_json, response_as_json["status"]

    try_until_success(api_call_collect_ticket)

    order_id = get_last_order_id(client, user_id, STATUS_COLLECTED)
    if order_id == None:
        raise Exception("Weird... There is no order to execute.")

    def api_call_enter_station():
        response = client.get(url=f"/api/v1/executeservice/execute/execute/{order_id}", name=get_name_suffix("enter_station"),
            context={'type': 'enter_station'})
        response_as_json = get_json_from_response(response)
        return response_as_json, response_as_json["status"]

    try_until_success(api_call_enter_station)

def get_voucher(client, user_id):
    order_id = get_last_order_id(client, user_id, STATUS_EXECUTED)
    if order_id == None:
        raise Exception("Weird... There is no order that was used.")

    def api_call_get_voucher():
        body = {"orderId": order_id, "type": 1}
        response = client.post(url=f"/getVoucher", json=body, name=get_name_suffix("get_voucher"), timeout=10,
            context={'type': 'get_voucher'})
        response_as_json = get_json_from_response(response)
        return response_as_json, response_as_json["status"]

    try_until_success(api_call_get_voucher)

class UserBooking(HttpUser):
    @events.request.add_listener
    def on_request(response_time, context, **kwargs):
        request_log_file.write(json.dumps({
            'time': time.perf_counter(),
            'latency': response_time / 1e3,
            'context': context,
        }) + '\n')

    def on_start(self, sleep=True):
        self.username, self.password = USER_POOL[0]
        if sleep:
            time.sleep(random.expovariate(lambd=1/INTERVAL))
        use_cache = False
        if len(USER_POOL) > 1:
            user_id, token, create_time = USER_POOL[-1]
            use_cache = time.time() - create_time < 1800
        if not use_cache:
            user_id, token = login(self.client, self.username, self.password)
            create_time = time.time()
            USER_POOL.append((user_id, token, create_time))
        self.client.headers.update({"Authorization": f"Bearer {token}"})
        self.client.headers.update({"Content-Type": "application/json"})
        self.client.headers.update({"Accept": "application/json"})
        self.user_id = user_id
        self.token_create_time = create_time

    def on_stop(self):
        pass

    @task
    def perform_task(self):
        request_id = str(uuid.uuid4())
        logging.debug(f'Running user "booking" with request id {request_id}...')

        home(self.client)
        search_departure(self.client)
        search_return(self.client)
        if random.randrange(10) == 0:
            book(self.client, self.user_id, self.username)

class CustomShape(LoadTestShape):
    time_limit = len(RPS)
    spawn_rate = 100

    def tick(self):
        run_time = self.get_run_time()
        if run_time < self.time_limit:
            user_count = RPS[int(run_time)]
            return (user_count, self.spawn_rate)
        return None
