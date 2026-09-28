# Monitoring Website on Linode with Python

A Python script that checks whether a web application running in a Docker container on a Linode server is up, emails you when it isn't, and tries to bring it back automatically.

## How it works

On a schedule, the script looks up the server's public IP address through the Linode API (using the server's label), sends an HTTP request to `http://<server-ip>:<APP_PORT>`, and acts on the result:

| Result | What the script does |
| --- | --- |
| Status `200` | Logs that the application is running. |
| Any other status code | The application answered with an error. Sends an "APPLICATION IS DOWN" email, then restarts the container. If that fails, reboots the server. |
| Connection refused | The server is up but nothing is listening on the port, which usually means the container is stopped. Sends an "APPLICATION IS DOWN" email, then restarts the container. If that fails, reboots the server. |
| No response within 10 seconds | The server itself is down or unreachable. Sends a "SITE IS DOWN" email, then reboots the server. |

If the application is still down after a reboot, the script sends a "MANUAL ACTION NEEDED" email and keeps running, so the next scheduled check tries again.

```
app down    ──► restart container ──► fixed
                      │ fails
                      ▼
server down ──► reboot server, then restart container ──► fixed
                      │ fails
                      ▼
               "MANUAL ACTION NEEDED" email
```

### Restarting the container

A booting server often accepts SSH connections before Docker is ready, so the container restart retries each step:

1. **Connect over SSH.** Each attempt waits up to 10 seconds to connect, with 10 seconds between attempts.
2. **Run `docker start <CONTAINER_NAME>`.** The script checks the command's exit status and retries 10 seconds apart, printing Docker's error each time.

The number of attempts depends on when the restart happens:

| When | Attempts per step | Longest wait for SSH | Longest wait for `docker start` |
| --- | --- | --- | --- |
| Before any reboot (the app is down, the server may be up) | 6 | About 2 minutes | About 1 minute |
| After a reboot (the server is still booting) | 12 | About 4 minutes | About 2 minutes |

If either step still fails after its attempts, the restart counts as failed. The script then escalates as shown above: a failed container restart leads to a reboot, and a failed restart after a reboot leads to the "MANUAL ACTION NEEDED" email.

This also covers a down server that reports "no route to host" instead of timing out. That failure looks like a refused connection, so the script first tries a container restart. The SSH attempts run out, and it falls back to a reboot.

### Rebooting the server

After asking Linode to reboot the server, the script waits in two stages:

1. **Wait for the reboot to begin.** For a few seconds after the request, Linode still reports the server as `running`. The script waits until the status changes (usually to `rebooting`), so it doesn't mistake that leftover `running` for a finished reboot.
2. **Wait for the server to come back.** The script waits until Linode reports `running` again, then restarts the container as described above.

### Schedule

The schedule is set at the bottom of [monitor-website.py](monitor-website.py). The check runs every 2 days at 00:00 (Europe/Warsaw time).

## Requirements

- Python 3.12
- [Pipenv](https://pipenv.pypa.io/)
- A Gmail account with an [app password](https://support.google.com/accounts/answer/185833) for sending alerts
- A Linode API token with read/write access to Linodes
- An SSH key that can log in to the server
- One Docker installation on the server, with the application in a named container (see [Server setup](#server-setup))

Python dependencies (installed by Pipenv): `requests`, `python-dotenv`, `paramiko`, `linode-api4`, `schedule`.

## Setup

1. Clone the repository and install the dependencies:

   ```bash
   git clone <repo-url>
   cd monitor-website
   pipenv install
   ```

2. Create a `.env` file in the project root (it is already listed in `.gitignore`):

   ```env
   EMAIL_ADDRESS=sender@gmail.com
   EMAIL_PASSWORD=your-gmail-app-password
   RECEIVER_EMAIL_ADDRESS=you@example.com
   LINODE_TOKEN=your-linode-api-token
   LINODE_LABEL=your-linode-label
   CONTAINER_NAME=nginx-app
   APP_PORT=8080
   SSH_USER=root
   SSH_KEY_PATH=/home/you/.ssh/your_key
   ```

   | Variable | Purpose |
   | --- | --- |
   | `EMAIL_ADDRESS`, `EMAIL_PASSWORD` | The Gmail account and app password the alerts are sent from. |
   | `RECEIVER_EMAIL_ADDRESS` | Where the alerts are sent. |
   | `LINODE_TOKEN` | Linode API token, used to look up and reboot the server. |
   | `LINODE_LABEL` | The server's label in the Linode dashboard. The script uses it to find the server and its public IP address, so there's no IP to keep up to date. |
   | `CONTAINER_NAME` | The name of the application's Docker container. |
   | `APP_PORT` | The port the application is published on. |
   | `SSH_USER`, `SSH_KEY_PATH` | The login the script uses to SSH into the server. |

   The script loads `.env` with `override=True`, so the values in `.env` always take priority over variables already set in your shell (for example, stale values left over from an earlier `pipenv shell`).

## Server setup

Run the application in a container with a fixed name and a restart policy:

```bash
docker run -d --name nginx-app --restart unless-stopped -p 8080:80 nginx
```

- **`--name`** lets the script restart the container by name. A container ID changes whenever the container is recreated.
- **`--restart unless-stopped`** makes Docker start the container automatically whenever Docker starts, including after a reboot. The script's `docker start` then acts as a safety net.
- **All Docker options must come before the image name** (`nginx`). Anything after the image name is passed to the container as its command.

To add a restart policy to a container that already exists, run `docker update --restart unless-stopped <container-name>`.

Keep **only one Docker installation** on the server. If both the snap and apt (`docker.io`) packages are installed, they run two separate Docker services. Each keeps its own set of containers, and after every reboot whichever starts last takes over the `docker` command, so `docker start` can fail with "No such container".

## Usage

```bash
pipenv run python monitor-website.py
```

The script runs in the foreground and keeps running until you stop it. To keep it running after you close the terminal, start it with a process manager such as `systemd`, `tmux`/`screen`, or `nohup`.

## Screenshots
- monitor-website.py terminal output
![monitor-website.py terminal output](https://res.cloudinary.com/dpav6x91z/image/upload/v1790592604/Screenshot_2026-09-28_122757_hsxlae.png)