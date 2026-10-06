# ShadowTraffic → Confluent Cloud (`datagen.users.enterprise`)

Produces synthetic Avro records into the `datagen.users.enterprise` topic on the
Confluent Cloud Enterprise cluster (`lkc-xxxxx`) in your Confluent Cloud environment, validated
against the already-registered `datagen.users-value` schema. No Confluent
Gateway in the path — this connects straight to the cluster over the
PrivateLink bootstrap endpoint.

Schema produced (matches the registered subject exactly):

```json
{
  "type": "record",
  "name": "users",
  "namespace": "ksql",
  "fields": [
    { "name": "registertime", "type": "long" },
    { "name": "userid",       "type": "string" },
    { "name": "regionid",     "type": "string" },
    { "name": "gender",       "type": "string" }
  ]
}
```

## Layout

```
config/shadowtraffic-config.json   # generator + connection definition (safe to commit)
config/client.properties.example   # template - copy to client.properties, fill in, gitignored
license.env.example                # template - copy to license.env, fill in, gitignored
.env.example                       # template - copy to .env (throughput knob), gitignored
run-sample.sh                      # dry run: 10 events to stdout, nothing sent to Kafka
run.sh                             # live run: produces to Kafka until Ctrl+C
```

## Before running

1. **Network reachability.** The bootstrap endpoint
   (`<cluster-id>.<region>.aws.private.confluent.cloud:9092`) only resolves
   over PrivateLink. The bastion (`ec2-user@<bastion-public-ip>`) is on that network
   but **does not have Docker installed** — you'll need to either:
   - install Docker on the bastion (`sudo yum install -y docker` / `sudo dnf install -y docker` depending on AMI, then `sudo systemctl start docker`), or
   - run this from a laptop/host that has a VPN or SSH tunnel into that VPC.

   Running it from an arbitrary machine with plain internet access will not
   resolve the endpoint.

2. **Fill in the templates** (all three are gitignored once created):
   ```
   cp license.env.example license.env        # your ShadowTraffic license
   cp .env.example .env                       # EVENTS_PER_SECOND, defaults to 5
   cp config/client.properties.example config/client.properties
   ```

3. **Populate `config/client.properties`:**
   - `bootstrap.servers` / the Schema Registry REST endpoint are already
     templated for `lkc-xxxxx` / `lsrc-xxxxx` — confirm the SR URL with
     `confluent schema-registry cluster describe --environment env-xxxxx`
     if it's changed.
   - Kafka API key/secret: from AWS Secrets Manager,
     `confluent/<env>/datagen-enterprise-kafka-creds`.
   - Schema Registry API key/secret: created alongside as
     `admin:schema_registry` in the same terraform apply — check whether it's
     bundled into `confluent/<env>/admin-enterprise-kafka-creds` or
     needs pulling from terraform output/state before filling
     `basic.auth.user.info`.

## Why `schemaRegistrySubject` is set explicitly

The registered subject is `datagen.users-value`, not the
`datagen.users.enterprise-value` that Confluent's default TopicNameStrategy
would expect for this topic. The config's `localConfigs.schemaRegistrySubject`
override tells ShadowTraffic to fetch that exact subject instead of guessing
from the topic name — leave it as-is.

## Running it

```bash
./run-sample.sh   # verify config + credentials first: prints 10 events, sends nothing
./run.sh          # live production, ~EVENTS_PER_SECOND events/sec, until Ctrl+C
```

`EVENTS_PER_SECOND` in `.env` controls throughput; edit and re-run to change
it (no config-file edit needed).
