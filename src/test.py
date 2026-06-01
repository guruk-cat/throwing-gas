import time
import sys

def delete_lines(n):
    for _ in range(n):
        # \033[F moves cursor up one line; \033[K clears that line
        sys.stdout.write("\033[F\033[K")

print("hello")

for i in range(11):
    # The \r resets the cursor, end="" prevents a new line
    print(f"Progress: {i * 10}%", flush=True)
    print(f"And.... still{i}!")
    delete_lines(2)
    time.sleep(0.5)

print("\nTask Complete!")