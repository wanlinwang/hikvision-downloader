# Hikvision/Hiwatch Video downloading script
A script for automatic downloading video/photo files from hikvision/hiwatch cameras via ISAPI interface.

Ready-to-use script is located in **release** folder.

## Security Configuration

Before running the script, you need to set the camera credentials via environment variables:

```bash
export HIK_USERNAME='your_username'
export HIK_PASSWORD='your_password'
```

**Note:** Never hardcode credentials in source code or commit them to version control.

## Usage

```
usage: 
  media_download.py [-u] [-p] CAM_IP START_DATE START_TIME END_DATE END_TIME

positional arguments:
  IP           camera's IP address
  START_DATE   start date of interval
  START_TIME   start time of interval
  END_DATE     end date of interval
  END_TIME     end time of interval

optional arguments:
  -h, --help   show this help message and exit
  -u, --utc    use parameters as UTC time, otherwise use as camera's local
               time
  -p, --photo  download photos instead of videos

Environment Variables:
  HIK_USERNAME: Camera username (required)
  HIK_PASSWORD: Camera password (required)

Examples:
  export HIK_USERNAME='admin' && export HIK_PASSWORD='yourpassword'
  media_download.py 10.10.10.10 2020-04-15 00:30:00 2020-04-15 10:59:59
  media_download.py -u 10.10.10.10 2020-04-15 00:30:00 2020-04-15 10:59:59
```

## Dependencies

- Python 3
- requests
- defusedxml (for secure XML parsing)