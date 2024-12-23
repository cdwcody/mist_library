'''
-------------------------------------------------------------------------------

    Written by Thomas Munzer (tmunzer@juniper.net)
    Github repository: https://github.com/tmunzer/Mist_library/

    This script is licensed under the MIT License.

-------------------------------------------------------------------------------
Python script trigger a snapshot/firmware backup on SRX devices.
This script is using the CSV report for the report_gateway_firmware.py script to
identify the SRX on which the command must be triggered.

-------
Requirements:
mistapi: https://pypi.org/project/mistapi/

-------
Usage:
This script can be run as is (without parameters), or with the options below.
If no options are defined, or if options are missing, the missing options will
be asked by the script or the default values will be used.

It is recommended to use an environment file to store the required information
to request the Mist Cloud (see https://pypi.org/project/mistapi/ for more 
information about the available parameters).

-------
Options:
-h, --help          display this help

-s, --site_id=      Set the site_id if only devices from a specific site must be 
                    processed. If not set, the script will process all the devices
                    from the report that need a firmware backup
-f, --in_file=      path to the report generated by the report_gateway_firmware script
                    default is "./report_gateway_firmware.csv"
--auto-approve      Does not ask for user confirmation before triggering the 
                    firmware backup API Calls

-l, --log_file=     define the filepath/filename where to write the logs
                    default is "./script.log"
-e, --env=          define the env file to use (see mistapi env file documentation 
                    here: https://pypi.org/project/mistapi/)
                    default is "~/.mist_env"

-------
Examples:
python3 ./fix_gateway_backup_firmware.py                  
python3 ./fix_gateway_backup_firmware.py --site_id=203d3d02-xxxx-xxxx-xxxx-76896a3330f4 

'''

#### IMPORTS #####
import sys
import csv
import getopt
import logging

MISTAPI_MIN_VERSION = "0.53.0"

try:
    import mistapi
    from mistapi.__logger import console as CONSOLE
except:
        print("""
        Critical: 
        \"mistapi\" package is missing. Please use the pip command to install it.

        # Linux/macOS
        python3 -m pip install mistapi

        # Windows
        py -m pip install mistapi
        """)
        sys.exit(2)



#### LOGS ####
LOGGER = logging.getLogger(__name__)

#### PARAMETERS #####
CSV_FILE = "./report_gateway_firmware.csv"
LOG_FILE = "./script.log"
ENV_FILE = "~/.mist_env"



#####################################################################
# PROGRESS BAR AND DISPLAY
class ProgressBar:
    def __init__(self):
        self.steps_total = 0
        self.steps_count = 0

    def _pb_update(self, size: int = 80):
        if self.steps_count > self.steps_total:
            self.steps_count = self.steps_total

        percent = self.steps_count / self.steps_total
        delta = 17
        x = int((size - delta) * percent)
        print(f"Progress: ", end="")
        print(f"[{'█'*x}{'.'*(size-delta-x)}]", end="")
        print(f"{int(percent*100)}%".rjust(5), end="")

    def _pb_new_step(
        self,
        message: str,
        result: str,
        inc: bool = False,
        size: int = 80,
        display_pbar: bool = True,
    ):
        if inc:
            self.steps_count += 1
        text = f"\033[A\033[F{message}"
        print(f"{text} ".ljust(size + 4, "."), result)
        print("".ljust(80))
        if display_pbar:
            self._pb_update(size)

    def _pb_title(
        self, text: str, size: int = 80, end: bool = False, display_pbar: bool = True
    ):
        print("\033[A")
        print(f" {text} ".center(size, "-"), "\n\n")
        if not end and display_pbar:
            print("".ljust(80))
            self._pb_update(size)

    def set_steps_total(self, steps_total: int):
        self.steps_total = steps_total

    def log_message(self, message, display_pbar: bool = True):
        self._pb_new_step(message, " ", display_pbar=display_pbar)

    def log_success(self, message, inc: bool = False, display_pbar: bool = True):
        LOGGER.info(f"{message}: Success")
        self._pb_new_step(
            message, "\033[92m\u2714\033[0m\n", inc=inc, display_pbar=display_pbar
        )

    def log_warning(self, message, inc: bool = False, display_pbar: bool = True):
        LOGGER.warning(f"{message}: Warning")
        self._pb_new_step(
            message, "\033[93m\u2B58\033[0m\n", inc=inc, display_pbar=display_pbar
        )

    def log_failure(self, message, inc: bool = False, display_pbar: bool = True):
        LOGGER.error(f"{message}: Failure")
        self._pb_new_step(
            message, "\033[31m\u2716\033[0m\n", inc=inc, display_pbar=display_pbar
        )

    def log_title(self, message, end: bool = False, display_pbar: bool = True):
        LOGGER.info(message)
        self._pb_title(message, end=end, display_pbar=display_pbar)


PB = ProgressBar()

###############################################################################
#### FUNCTIONS ####
def _process_gateways(apisession:mistapi.APISession, gateways:list) -> list:
    i=0
    PB.set_steps_total(len(gateways))
    for gateway in gateways:
        site_id = gateway.get("cluster_site_id")
        device_id = gateway.get("cluster_device_id")
        device_mac = gateway.get("module_mac")
        message = f"Processing device {device_id}"
        PB.log_message(message)
        if not site_id:
            PB.log_failure(message, inc=True)
            CONSOLE.error(f"Missing site_id for device {device_mac}")
            continue
        if not device_id:
            PB.log_failure(message, inc=True)
            CONSOLE.error(f"Missing device_id for device {device_mac}")
            continue
        try:
            resp = mistapi.api.v1.sites.devices.createSiteDeviceSnapshot(apisession, site_id, device_id)
            if resp.status_code == 200:
                PB.log_success(message, inc=True)
            else:
                PB.log_failure(message, inc=True)
        except:
            PB.log_failure(message, inc=True)
            LOGGER.error("Exception occurred", exc_info=True)

### READ REPORT
def _read_csv(csv_file:str, site_id:str) -> list:
    data = []
    device_ids = []
    message="Reading CSV Report"
    PB.log_message(message, display_pbar=False)
    try:
        with open(csv_file, newline='') as f:
            reader = csv.DictReader(filter(lambda row: row[0]!='#', f))
            for row in reader:
                if not "SRX" in row.get("module_model"):
                    continue
                if site_id and row.get("cluster_site_id") != site_id:
                    continue
                if row.get("module_need_snapshot") != "True": 
                    continue
                if row.get("cluster_device_id") in device_ids:
                    continue
                data.append(row)
                device_ids.append(row.get("cluster_device_id"))
        PB.log_success(message, inc=False, display_pbar=False)
    except:
        PB.log_failure(message, inc=False, display_pbar=False)
        LOGGER.error("Exception occurred", exc_info=True)
        sys.exit(1)
    return data

def _request_approval(data:dict):
    print("".center(80, "-"))
    print("List of gateways to process:")
    print()
    mistapi.cli.pretty_print(data)
    r = input("Do you want to continue (y/N)? ")
    if r.lower() == "y":
        print("".center(80, "-"))
        return
    else:
        CONSOLE.info("process stopped by the user. Exiting...")
        sys.exit(0)


###############################################################################
### START
def _start(apisession: mistapi.APISession, site_id: str, csv_file:str=CSV_FILE, auto_approve:bool=False) -> None:

    data = _read_csv(csv_file, site_id)
    if not data:
        print("All the gateways are compliant... Exiting...")
        sys.exit(0)
    if auto_approve:
        CONSOLE.info("auto-approve parameter has been set to True. Starting the process")
    else:
        _request_approval(data)
    _process_gateways(apisession, data)


###############################################################################
### USAGE
def usage():
    print('''
-------------------------------------------------------------------------------

    Written by Thomas Munzer (tmunzer@juniper.net)
    Github repository: https://github.com/tmunzer/Mist_library/

    This script is licensed under the MIT License.

-------------------------------------------------------------------------------
Python script trigger a snapshot/firmware backup on SRX devices.
This script is using the CSV report for the report_gateway_firmware.py script to
identify the SRX on which the command must be triggered.

-------
Requirements:
mistapi: https://pypi.org/project/mistapi/

-------
Usage:
This script can be run as is (without parameters), or with the options below.
If no options are defined, or if options are missing, the missing options will
be asked by the script or the default values will be used.

It is recommended to use an environment file to store the required information
to request the Mist Cloud (see https://pypi.org/project/mistapi/ for more 
information about the available parameters).

-------
Options:
-h, --help          display this help

-s, --site_id=      Set the site_id if only devices from a specific site must be 
                    processed. If not set, the script will process all the devices
                    from the report that need a firmware backup
-f, --in_file=      path to the report generated by the report_gateway_firmware script
                    default is "./report_gateway_firmware.csv"
--auto-approve      Does not ask for user confirmation before triggering the 
                    firmware backup API Calls

-l, --log_file=     define the filepath/filename where to write the logs
                    default is "./script.log"
-e, --env=          define the env file to use (see mistapi env file documentation 
                    here: https://pypi.org/project/mistapi/)
                    default is "~/.mist_env"

-------
Examples:
python3 ./fix_gateway_backup_firmware.py                  
python3 ./fix_gateway_backup_firmware.py --site_id=203d3d02-xxxx-xxxx-xxxx-76896a3330f4 

''')
    sys.exit(0)

def check_mistapi_version():
    if mistapi.__version__ < MISTAPI_MIN_VERSION:
        LOGGER.critical(f"\"mistapi\" package version {MISTAPI_MIN_VERSION} is required, you are currently using version {mistapi.__version__}.")
        LOGGER.critical(f"Please use the pip command to updated it.")
        LOGGER.critical("")
        LOGGER.critical(f"    # Linux/macOS")
        LOGGER.critical(f"    python3 -m pip install --upgrade mistapi")
        LOGGER.critical("")
        LOGGER.critical(f"    # Windows")
        LOGGER.critical(f"    py -m pip install --upgrade mistapi")
        print(f"""
    Critical: 
    \"mistapi\" package version {MISTAPI_MIN_VERSION} is required, you are currently using version {mistapi.__version__}. 
    Please use the pip command to updated it.

    # Linux/macOS
    python3 -m pip install --upgrade mistapi

    # Windows
    py -m pip install --upgrade mistapi
        """)
        sys.exit(2)
    else: 
        LOGGER.info(f"\"mistapi\" package version {MISTAPI_MIN_VERSION} is required, you are currently using version {mistapi.__version__}.")



###############################################################################
### ENTRY POINT
if __name__ == "__main__":
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hs:f:e:l:", ["help", "site_id", "in_file=", "auto-approve", "env=", "log_file="])
    except getopt.GetoptError as err:
        CONSOLE.error(err)
        usage()

    SITE_ID=None
    AUTO_APPROVE=False
    for o, a in opts:
        if o in ["-h", "--help"]:
            usage()
        elif o in ["-s", "--site_id"]:
            SITE_ID = a
        elif o in ["-f", "--in_file"]:
            CSV_FILE=a
        elif o in ["--auto-approve"]:
            AUTO_APPROVE=True
        elif o in ["-e", "--env"]:
            ENV_FILE=a
        elif o in ["-l", "--log_file"]:
            LOG_FILE = a

        else:
            assert False, "unhandled option"

    #### LOGS ####
    logging.basicConfig(filename=LOG_FILE, filemode='w')
    LOGGER.setLevel(logging.DEBUG)
    check_mistapi_version()
    ### MIST SESSION ###
    APISESSION = mistapi.APISession(env_file=ENV_FILE)
    APISESSION.login()
    ### START ###
    _start(APISESSION, SITE_ID, CSV_FILE, AUTO_APPROVE)