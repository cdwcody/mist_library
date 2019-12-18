'''
Python script to invite/add adminsitrators from a CSV file.
The CSV file must have 3 rows: email, first name, last name

You can run the script with the command "python3 org_admins_import.py <path_to_the_csv_file>"

The script has 3 different steps:
1) admin login
2) select the organisation where you want to add/invite the admins
3) choose if you want to give access to the whole organisation, or only to specific sites
'''
import mlib as mist_lib
from tabulate import tabulate
import mlib.cli as cli
import sys
import csv
#### PARAMETERS #####
csv_separator = ","
privileges = []
    
mist = mist_lib.Mist_Session()

roles = {"s": "admin", "n": "write", "o": "read", "h":"helpdesk"}
role = ""
if privileges == []:
    org_id = cli.select_org(mist)
    while role not in roles:
        role = input("Which level of privilege at the org level (\"s\" for Super Admin, \"n\" for Network Admin,\"o\" for observer,\"h\" for helpdesk)")    
    while True:
        all_sites = input("Do you want to select specific sites (y/N)?")
        if all_sites.lower()=="y": 
            site_ids = cli.select_site(mist, org_id, True)
            for site_id in site_ids:
                privileges.append({"scope": "site", "org_id": org_id, "site_id": site_id, "role":roles[role]})
            break
        elif all_sites.lower() == "n" or all_sites == "":            
            site_ids = mist_lib.org.sites.get(mist, org_id)
            privileges.append({"scope": "org", "org_id": org_id, "site_id":site_ids["result"][0], "role":roles[role]})
            break



print("Opening CSV file %s" % sys.argv[1])
try:
    with open(sys.argv[1], 'r') as my_file:
        invite_file = csv.reader(my_file, delimiter=',')
        for row in invite_file:  
            email= row[0]
            first_name= row[1]
            last_name = row[2]        
            print(', '.join(row))
            mist_lib.requests.org.admins.create_invite(mist, org_id, email, privileges, first_name, last_name)            
except:
    print("Error while opening the CSV file... Aborting")

admins = mist_lib.requests.org.admins.get(mist, org_id)['result']
print(tabulate(admins))
#print(admins)
exit(0)