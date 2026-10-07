//! R17 diagnostics from the existing acquisition; never opens or reads a bus.
use duck_control::feetech::SyncTrace;
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Clone, Default, Serialize)]
pub struct DeviceCounts {
    pub missing: u64,
    pub timeout: u64,
    pub consecutive_missing: u64,
    pub consecutive_timeout: u64,
    pub last_missing_read: Option<u64>,
    pub last_timeout_read: Option<u64>,
}

#[derive(Clone, Serialize)]
pub struct CommunicationStats {
    pub classification: &'static str,
    pub session: String,
    pub total_reads: u64,
    pub unsent_reads: u64,
    pub complete_but_late: u64,
    pub incomplete_timeout_reads: u64,
    pub missing_reads: u64,
    pub by_id: BTreeMap<u8, DeviceCounts>,
    pub last_trace: SyncTrace,
}

impl CommunicationStats {
    pub fn new(ids: impl IntoIterator<Item = u8>) -> Self {
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        Self {
            classification: "exclusive-v2",
            session: format!("{}-{stamp}", std::process::id()),
            total_reads: 0,
            unsent_reads: 0,
            complete_but_late: 0,
            incomplete_timeout_reads: 0,
            missing_reads: 0,
            by_id: ids
                .into_iter()
                .map(|id| (id, DeviceCounts::default()))
                .collect(),
            last_trace: SyncTrace::default(),
        }
    }

    pub fn observe(&mut self, trace: &SyncTrace) {
        // Torque / gain confirmations cannot overwrite the evidence or increment it.
        if (trace.address, trace.length) != (56, 15) {
            return;
        }
        self.total_reads = self.total_reads.saturating_add(1);
        self.last_trace = trace.clone();
        if !trace.request_sent {
            self.unsent_reads = self.unsent_reads.saturating_add(1);
            return;
        }
        if trace.missing_ids.is_empty() && trace.complete_but_late {
            self.complete_but_late = self.complete_but_late.saturating_add(1);
        }
        let missing: BTreeSet<_> = trace.missing_ids.iter().copied().collect();
        if !missing.is_empty() {
            if trace.deadline_exceeded {
                self.incomplete_timeout_reads = self.incomplete_timeout_reads.saturating_add(1);
            } else {
                self.missing_reads = self.missing_reads.saturating_add(1);
            }
        }
        for (id, counts) in &mut self.by_id {
            if missing.contains(id) {
                // A deadline cannot establish permanent packet loss. Keep the
                // two causes exclusive; never charge every ID for a late batch.
                if trace.deadline_exceeded {
                    counts.timeout = counts.timeout.saturating_add(1);
                    counts.consecutive_timeout = counts.consecutive_timeout.saturating_add(1);
                    counts.consecutive_missing = 0;
                    counts.last_timeout_read = Some(self.total_reads);
                } else {
                    counts.missing = counts.missing.saturating_add(1);
                    counts.consecutive_missing = counts.consecutive_missing.saturating_add(1);
                    counts.consecutive_timeout = 0;
                    counts.last_missing_read = Some(self.total_reads);
                }
            } else {
                counts.consecutive_missing = 0;
                counts.consecutive_timeout = 0;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn counts_every_acquisition_and_preserves_each_device_after_recovery() {
        let mut stats = CommunicationStats::new([14, 32, 200]);
        let mut trace = SyncTrace {
            address: 56,
            length: 15,
            request_sent: true,
            missing_ids: vec![32, 32],
            deadline_exceeded: true,
            partial_received: true,
            ..Default::default()
        };
        stats.observe(&trace);
        trace.missing_ids = vec![14, 32];
        trace.deadline_exceeded = false;
        stats.observe(&trace);
        trace.missing_ids.clear();
        stats.observe(&trace);
        assert_eq!(stats.total_reads, 3);
        assert_eq!((stats.by_id[&32].missing, stats.by_id[&32].timeout), (1, 1));
        assert_eq!(stats.by_id[&32].last_missing_read, Some(2));
        assert_eq!(stats.by_id[&32].consecutive_missing, 0);
        assert_eq!(stats.by_id[&32].consecutive_timeout, 0);
        assert_eq!(stats.by_id[&32].last_timeout_read, Some(1));
        assert_eq!(
            (stats.incomplete_timeout_reads, stats.missing_reads),
            (1, 1)
        );
        assert_eq!((stats.by_id[&14].missing, stats.by_id[&14].timeout), (1, 0));
        assert_eq!(stats.by_id[&200].missing, 0);
    }

    #[test]
    fn unsent_and_complete_late_reads_do_not_blame_individual_devices() {
        let mut stats = CommunicationStats::new([14, 32, 200]);
        let mut trace = SyncTrace {
            address: 56,
            length: 15,
            request_sent: false,
            missing_ids: vec![14, 32, 200],
            deadline_exceeded: true,
            ..Default::default()
        };
        stats.observe(&trace);
        trace.request_sent = true;
        trace.missing_ids.clear();
        trace.complete_but_late = true;
        stats.observe(&trace);
        trace.address = 40;
        trace.length = 1;
        stats.observe(&trace);
        assert_eq!(
            (
                stats.total_reads,
                stats.unsent_reads,
                stats.complete_but_late
            ),
            (2, 1, 1)
        );
        assert!(
            stats
                .by_id
                .values()
                .all(|v| v.missing == 0 && v.timeout == 0)
        );
        assert_eq!(stats.last_trace.address, 56);
        assert_ne!(stats.session, CommunicationStats::new([14]).session);
    }

    #[test]
    fn screenshot_partial_read_is_only_timeout_and_recovery_keeps_history() {
        let mut stats = CommunicationStats::new([10, 20, 31, 34, 200]);
        let mut trace = SyncTrace {
            address: 56,
            length: 15,
            request_sent: true,
            missing_ids: vec![10, 31, 34],
            elapsed_us: 30_005,
            deadline_exceeded: true,
            partial_received: true,
            ..Default::default()
        };
        stats.observe(&trace);
        stats.observe(&trace);
        assert_eq!(stats.by_id[&34].timeout, 2);
        assert_eq!(stats.by_id[&34].missing, 0);
        assert_eq!(stats.by_id[&34].consecutive_timeout, 2);
        assert_eq!(stats.by_id[&20].timeout, 0);
        trace.missing_ids.clear();
        trace.partial_received = false;
        trace.deadline_exceeded = false;
        stats.observe(&trace);
        assert_eq!(stats.by_id[&34].consecutive_timeout, 0);
        assert_eq!(stats.by_id[&34].last_timeout_read, Some(2));
        assert_eq!(stats.by_id[&34].timeout, 2);
        assert_eq!(stats.complete_but_late, 0);
    }

    #[test]
    fn protocol_failure_after_deadline_is_not_a_complete_late_frame() {
        let mut stats = CommunicationStats::new([14]);
        stats.observe(&SyncTrace {
            address: 56,
            length: 15,
            request_sent: true,
            deadline_exceeded: true,
            bad_checksums: 1,
            ..Default::default()
        });
        assert_eq!(stats.complete_but_late, 0);
        assert_eq!(stats.by_id[&14].timeout, 0);
        assert_eq!(stats.by_id[&14].missing, 0);
    }
}
