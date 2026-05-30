import duckdb, os

path = os.environ.get("DUCKDB_PATH", "retail.duckdb")
con = duckdb.connect(path)
df = con.execute("SHOW ALL TABLES").fetchdf()
print(df[["schema", "name"]].to_string())