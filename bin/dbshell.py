import os

dbname = os.environ.get("PROD_PGDBNAME")
pgpass = os.environ.get("PROD_PGPASS")
pguser = os.environ.get("PROD_PGUSER")
pghost = os.environ.get("PROD_PGHOST")
pgport = os.environ.get("PROD_PGPORT")

admindbname = os.environ.get("PROD_ADMIN_PGDBNAME")
adminpguser = os.environ.get("PROD_ADMIN_PGUSER")
adminpgpass = os.environ.get("PROD_ADMIN_PGPASS")

if __name__ == "__main__":
    os.system(f"PGSSLMODE=require PGPASSWORD={adminpgpass} psql -U {adminpguser} -h {pghost} -p {pgport} -d {admindbname}")
