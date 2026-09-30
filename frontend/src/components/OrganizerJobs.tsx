import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { OrganizerConfiguration, OrganizerJob } from "../types";

export function OrganizerJobs() {
  const [configurations, setConfigurations] = useState<OrganizerConfiguration[]>([]);
  const [jobs, setJobs] = useState<OrganizerJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [configurationData, jobData] = await Promise.all([
        api.getOrganizerConfigurations(),
        api.getOrganizerJobs(),
      ]);
      setConfigurations(configurationData);
      setJobs(jobData);
      setError(null);
    } catch (value) {
      setError(value instanceof Error ? value.message : String(value));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!jobs.some((job) => ["PENDING", "RUNNING"].includes(job.status))) {
      return;
    }
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(timer);
  }, [jobs, refresh]);

  const run = async (configuration: OrganizerConfiguration, dryRun: boolean) => {
    setBusy(true);
    try {
      await api.runOrganizer(configuration.id, dryRun);
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  const loadJobDetails = async (job: OrganizerJob) => {
    if (job.operations) return;
    try {
      const [detail, operations] = await Promise.all([
        api.getOrganizerJob(job.id),
        api.getOrganizerOperations(job.id),
      ]);
      detail.operations = operations;
      setJobs((current) =>
        current.map((item) => (item.id === detail.id ? detail : item))
      );
    } catch (value) {
      setError(value instanceof Error ? value.message : String(value));
    }
  };

  return (
    <section>
      <h2>Organizer</h2>
      {error && <p className="error">{error}</p>}
      <h3>Configurations</h3>
      {configurations.map((configuration) => (
        <article key={configuration.id}>
          <strong>{configuration.name}</strong>{" "}
          <span>
            {configuration.adapter}: {configuration.source} → {configuration.destination}
          </span>
          <button disabled={busy} onClick={() => void run(configuration, true)}>
            Dry run
          </button>
          <button disabled={busy} onClick={() => void run(configuration, false)}>
            Run
          </button>
        </article>
      ))}
      <h3>Recent jobs</h3>
      {jobs.map((job) => (
        <details
          key={job.id}
          onToggle={(event) => {
            if (event.currentTarget.open) void loadJobDetails(job);
          }}
        >
          <summary>
            Job {job.id}: {job.status} {job.dry_run ? "(dry run)" : ""}
          </summary>
          {job.error && <p className="error">{job.error}</p>}
          <ul>
            {(job.operations ?? []).map((operation) => (
              <li key={operation.id}>
                {operation.status}: {operation.source}
                {operation.destination ? ` → ${operation.destination}` : ""}
              </li>
            ))}
          </ul>
        </details>
      ))}
    </section>
  );
}
