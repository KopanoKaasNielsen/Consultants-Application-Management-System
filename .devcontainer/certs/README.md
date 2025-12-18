Put your corporate/organization CA certificate in this folder if your proxy intercepts HTTPS.

- File name expected by the devcontainer: `devcontainer-extra-ca.crt`
- Format: PEM encoded X.509 certificate (`-----BEGIN CERTIFICATE-----`)
- This folder ignores `*.crt`/`*.pem` via `.gitignore` so you don’t accidentally commit private CAs.

After placing the file, rebuild the devcontainer (or run `bash .devcontainer/setup-proxy-ca.sh` inside the container).
