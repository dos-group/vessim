Base workload to run on a client

1. Install the requirements: `pip3 install -r requirements.txt`
2. Run the PyTorch training script in the background: `python pytorch_training.py &` 
    - Via `jobs` you can list background jobs and retrieve them via `fg`
3. Store PID of the last executed process in variable: `pytorch=$!`

TODO:
- `cpulimit`?
- Measure CPU usage of process?
  - e.g. `top -b -n 2 -d 1 -p $pytorch | tail -1 | awk '{print $9}'` (https://stackoverflow.com/a/52751050/5373209)
