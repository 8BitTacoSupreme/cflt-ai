# =============================================================================
# FSI Kafka Platform — share_group_topic Module
# =============================================================================
# Provisions a governed topic intended for SHARE-GROUP (queue) consumption,
# plus least-privilege RBAC for the producer and the share-group worker pool.
#
# Share groups (KIP-932) are at-least-once and do NOT preserve per-key order.
# This module refuses to back a `critical` SLA tier unless the caller explicitly
# acknowledges that via allow_at_least_once — a tripwire against putting ordered
# / exactly-once regulatory state changes on a queue. See ../../../wiki/concepts/
# queues-for-kafka-share-groups.md.
#
# Usage:
#   module "screening_task_queue" {
#     source           = "../../modules/share_group_topic"
#     domain           = "ofac"
#     application      = "screening"
#     schema_version   = "v1"
#     entity           = "screening-task"
#     owner            = "screening-team@example.com"
#     share_group_id   = "ofac-screening-workers"
#     kafka_cluster_id = var.kafka_cluster_id
#     producer_service_accounts = ["sa-ofac-intake"]
#     consumer_service_accounts = ["sa-ofac-worker-1", "sa-ofac-worker-2"]
#   }
# =============================================================================

terraform {
  required_providers {
    confluent = {
      source  = "confluentinc/confluent"
      version = "~> 2.0"
    }
  }
}

locals {
  # Queue topics carry a -queue suffix so naming makes the consumption model explicit.
  topic_name = "${var.domain}.${var.application}.${var.schema_version}.${var.entity}-queue"
}

resource "confluent_kafka_topic" "this" {
  kafka_cluster {
    id = var.kafka_cluster_id
  }
  topic_name       = local.topic_name
  partitions_count = var.partitions

  config = {
    # Durable writes — FSI baseline regardless of consumption model.
    "min.insync.replicas" = "2"
    "cleanup.policy"      = "delete"
  }

  # FSI tripwire: a queue (at-least-once, unordered) may not back a 'critical'
  # SLA tier unless the caller explicitly accepts those semantics.
  lifecycle {
    precondition {
      condition     = !(var.sla_tier == "critical" && !var.allow_at_least_once)
      error_message = "sla_tier=critical on a share-group topic requires allow_at_least_once=true (share groups are at-least-once and unordered)."
    }
  }
}

# Producer: write to the queue topic.
resource "confluent_role_binding" "producers" {
  for_each    = toset(var.producer_service_accounts)
  principal   = "User:${each.value}"
  role_name   = "DeveloperWrite"
  crn_pattern = "${confluent_kafka_topic.this.kafka_cluster[0].id}/topic=${local.topic_name}"
}

# Share-group workers: read the topic AND operate the named share group.
# Both grants are required for share-group consumption (KIP-932 RBAC).
resource "confluent_role_binding" "consumer_topic_read" {
  for_each    = toset(var.consumer_service_accounts)
  principal   = "User:${each.value}"
  role_name   = "DeveloperRead"
  crn_pattern = "${confluent_kafka_topic.this.kafka_cluster[0].id}/topic=${local.topic_name}"
}

resource "confluent_role_binding" "consumer_share_group_read" {
  for_each    = toset(var.consumer_service_accounts)
  principal   = "User:${each.value}"
  role_name   = "DeveloperRead"
  crn_pattern = "${confluent_kafka_topic.this.kafka_cluster[0].id}/group=${var.share_group_id}"
}
