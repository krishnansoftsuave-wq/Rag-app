# NovaCloud Python SDK 3.x reference

Applies to: novacloud-sdk 3.0 and later (current release 3.4.1)

## Client

    from novacloud import Client

    client = Client(api_key="YOUR_API_KEY", region="us-east")

NovaClient.connect() was deprecated in 3.0 and removed in 3.2. Use Client(api_key=...) instead.

## Objects API

The Objects API stores files in NovaObject buckets. Every object operation lives under client.objects.

client.objects.upload(bucket, key, path_or_file, metadata=None) streams the file in parts, so it works for files
of any size up to 5 TB:

    client.objects.upload("my-bucket", "reports/report.pdf", "report.pdf", metadata={"owner": "finance"})

client.objects.download(bucket, key, destination) writes an object to a local path.

## Deprecations

| Deprecated (2.x)            | Replacement (3.x)                 | Status                        |
|-----------------------------|-----------------------------------|-------------------------------|
| NovaClient.connect()        | Client(api_key=...)               | removed in 3.2                |
| client.put_object()         | client.objects.upload()           | deprecated in 3.0, removed 3.2|
| client.put_object_multipart | client.objects.upload()           | removed in 3.2                |
| client.get_object()         | client.objects.download()         | deprecated in 3.0, removed 3.2|

Calling a removed method raises AttributeError. New code must use the 3.x methods.

## Legacy support (2.x)

Applications that cannot upgrade yet can pin novacloud-sdk<3.0. On 2.x, client.put_object() and
client.get_object() keep working, and 2.x receives security fixes until 2026-12-31.
