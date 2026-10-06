# =============================================================================
# share_group_topic — Module Inputs
# =============================================================================
# Mirrors the governance inputs of modules/topic, adding share-group (queue)
# consumption controls. See README.md for the lock-step landing checklist.

# ---------------------------------------------------------------------------
# Topic identity (required — assembles the topic name)
# ---------------------------------------------------------------------------
variable "domain" {
  description = "Business domain (e.g., payments, rtfd, ofac)"
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.domain))
    error_message = "Domain must be lowercase alphanumeric with hyphens, 2-31 chars, starting with a letter."
  }
}

variable "application" {
  description = "Application name within the domain (e.g., screening, fraud-cases)"
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.application))
    error_message = "Application must be lowercase alphanumeric with hyphens, 2-31 chars."
  }
}

variable "schema_version" {
  description = "Schema version identifier (e.g., v1, v2)"
  type        = string
  validation {
    condition     = can(regex("^v[0-9]+$", var.schema_version))
    error_message = "Version must follow the pattern v1, v2, etc."
  }
}

variable "entity" {
  description = "The work-item entity this queue carries (e.g., screening-task, fraud-case)"
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,60}$", var.entity))
    error_message = "Entity must be lowercase alphanumeric with hyphens, 2-61 chars."
  }
}

# ---------------------------------------------------------------------------
# Governance metadata (required)
# ---------------------------------------------------------------------------
variable "owner" {
  description = "Team email responsible for this queue topic (e.g., screening-team@example.com)"
  type        = string
  validation {
    condition     = can(regex("^[^@]+@[^@]+\\.[^@]+$", var.owner))
    error_message = "Owner must be a valid email address."
  }
}

variable "sla_tier" {
  description = "SLA tier. Share groups are at-least-once and unordered; 'critical' requires allow_at_least_once."
  type        = string
  default     = "standard"
  validation {
    condition     = contains(["standard", "high", "critical"], var.sla_tier)
    error_message = "sla_tier must be one of: standard, high, critical."
  }
}

# ---------------------------------------------------------------------------
# Share-group (queue) controls
# ---------------------------------------------------------------------------
variable "share_group_id" {
  description = "The share group that consumes this topic (queue worker pool identity)."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9._-]{1,80}$", var.share_group_id))
    error_message = "share_group_id must be lowercase, start with a letter, 2-81 chars."
  }
}

variable "partitions" {
  description = "Partition count. With share groups, consumer parallelism is NOT bound by this; size for throughput/retention, not worker count."
  type        = number
  default     = 6
}

variable "allow_at_least_once" {
  description = "Explicit acknowledgement that at-least-once + unordered delivery is acceptable for this data. Required when sla_tier = critical."
  type        = bool
  default     = false
}

variable "consumer_service_accounts" {
  description = "Service accounts for the share-group worker pool (granted DeveloperRead on topic + share group)."
  type        = list(string)
  default     = []
}

variable "producer_service_accounts" {
  description = "Service accounts that enqueue work onto this topic."
  type        = list(string)
  default     = []
}

variable "kafka_cluster_id" {
  description = "Target Confluent cluster ID. The cluster must have the share-group feature enabled (see README cluster prerequisites)."
  type        = string
}
