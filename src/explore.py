"""Step 1: a first look at the World Bank remittance price data."""
import sys
import pandas as pd

path = sys.argv[1]  # path to the Excel file

# 1. Which sheets are in the workbook?
xl = pd.ExcelFile(path)
print("Sheets:", xl.sheet_names)

# 2. Load the main data sheet (first 41 columns only)
df = pd.read_excel(path, sheet_name="Dataset (from Q2 2016)", usecols=range(41))
print("\nRows, columns:", df.shape)

# 3. Which periods does it cover?
print("\nLast 5 periods (number of quotes each):")
print(df["period"].value_counts().sort_index().tail(5))

# 4. The headline check: average total cost of sending $200 in Q3 2025
q3 = df[df["period"] == "2025_3Q"]
avg = pd.to_numeric(q3["cc1 total cost %"], errors="coerce").mean()
print(f"\nAverage cost of sending $200, Q3 2025: {avg:.2f}%  (World Bank reports 6.36%)")

# 5. How many of those quotes start in the United States?
us = q3[q3["source_code"] == "USA"]
print("US-origin quotes in Q3 2025:", len(us))
