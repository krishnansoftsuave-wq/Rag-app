# Uploading files to a bucket with the NovaCloud Python SDK

Applies to: novacloud-sdk 2.x
Last updated: 2024-03-11

This guide shows how to upload a file to a NovaObject bucket from Python, how to set metadata on the uploaded
file, and how to download it again.

## Install and connect

Install the SDK with pip:

    pip install novacloud-sdk==2.9.4

Create a client with your API key:

    from novacloud import NovaClient

    client = NovaClient.connect("YOUR_API_KEY", region="us-east")

## Upload a file to a bucket

Use put_object to upload a file to a bucket. Pass the bucket name, the object key and the file contents:

    with open("report.pdf", "rb") as f:
        client.put_object("my-bucket", "reports/report.pdf", f.read())

To set metadata on the uploaded file, pass a metadata dictionary:

    client.put_object("my-bucket", "reports/report.pdf", data, metadata={"owner": "finance"})

put_object reads the whole file into memory, so for files larger than 100 MB use put_object_multipart.

## Download a file

    data = client.get_object("my-bucket", "reports/report.pdf")

## Errors

put_object raises NovaError when the bucket does not exist or the API key cannot write to it.
