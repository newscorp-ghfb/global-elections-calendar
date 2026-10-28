// The worker's event routing (P131). Pure: Chrome's events are wired to these in background.js,
// so the order of calls can be tested without waiting for the events themselves.

export const ALARM_NAME = "elections-refresh";

// Each handler returns a promise, except `message`, which returns undefined at once for a
// message that is not a check request (so the caller knows not to hold the reply channel open).
export function handlers({ runCheck, ensureAlarm, isDue, openHelp }) {
  return {
    async installed(details) {
      if (details.reason === "install") {
        try {
          await openHelp();
        } catch (err) {
          console.error(err); // a help tab that cannot open must not stop the alarm or the check
        }
      }
      await ensureAlarm();
      await runCheck();
    },
    async startup() {
      await ensureAlarm();
      await runCheck();
    },
    async alarm(alarm) {
      if (alarm.name !== ALARM_NAME) return;
      try {
        await runCheck();
      } finally {
        await ensureAlarm(); // kept even when the check rejects
      }
    },
    message(msg) {
      if (typeof msg !== "object" || msg === null || msg.type !== "CHECK") return undefined;
      return (async () => {
        await ensureAlarm();
        if (msg.force || (await isDue())) return runCheck();
        return { ok: true, changed: false, skipped: true };
      })();
    },
  };
}
