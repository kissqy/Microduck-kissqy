//! Startup parameters — re-exported from the `robotd-params` crate.
//!
//! The types moved out so `robotctl configure` can edit the file with the real schema, the
//! real defaults and the real validation instead of a copy that drifts. Everything is
//! re-exported here under the module name the rest of this daemon always used.

pub use robotd_params::*;
