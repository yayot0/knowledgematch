import sys, sqlite3
import pandas, numpy, sklearn, streamlit

print("=== Entorno KnowledgeMatch ===")
print(f"Python       {sys.version.split()[0]}")
print(f"pandas       {pandas.__version__}")
print(f"NumPy        {numpy.__version__}")
print(f"scikit-learn {sklearn.__version__}")
print(f"Streamlit    {streamlit.__version__}")
print(f"SQLite       {sqlite3.sqlite_version}")
print("Entorno listo ✔")