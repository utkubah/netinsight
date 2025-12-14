# netinsight/main.py
import time

from . import ping_test, dns_test, http_test

INTERVAL_SECONDS = 30  # how often to run tests

def run_once():
    ping_result = ping_test.run_ping("8.8.8.8")
    dns_result = dns_test.run_dns("www.google.com")
    http_result = http_test.run_http("https://www.google.com")

    # TODO: write to log file and/or stdout
    print(ping_result, dns_result, http_result)

def main():
    while True:
        run_once()
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
