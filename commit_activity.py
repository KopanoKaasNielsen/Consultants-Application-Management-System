import subprocess
import matplotlib.pyplot as plt
from collections import Counter
from datetime import datetime

# Run git log to get commit dates
git_log_output = subprocess.check_output(
    ["git", "log", "--pretty=format:%ad", "--date=short"],
    universal_newlines=True
)

# Parse dates and count commits per day
commit_dates = git_log_output.strip().split('\n')
commit_counts = Counter(commit_dates)

# Sort dates
sorted_dates = sorted(commit_counts.keys())
sorted_counts = [commit_counts[date] for date in sorted_dates]

# Convert date strings to datetime objects for plotting
date_objects = [datetime.strptime(date, "%Y-%m-%d") for date in sorted_dates]

# Plot commit activity as a bar chart
plt.figure(figsize=(12, 6))
plt.bar(date_objects, sorted_counts, color='skyblue')
plt.title("Git Commit Activity Over Time")
plt.xlabel("Date")
plt.ylabel("Number of Commits")
plt.xticks(rotation=45)
plt.tight_layout()
plt.grid(True)

# Save the plot
plt.savefig("commit_activity.png")
plt.show()
