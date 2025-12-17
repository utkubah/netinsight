# netinsight/main.py
import time

from . import ping_check, dns_check, http_check

INTERVAL_SECONDS = 30  # how often to run tests

def run_once():
    ping_result = ping_check.run_ping("8.8.8.8")
    dns_result = dns_check.run_dns("www.google.com")
    http_result = http_check.run_http("https://www.goolsgle.com")

    # TODO: write to log file and/or stdout
    print(ping_result, dns_result, http_result)

def main():
    while True:
        run_once()
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
