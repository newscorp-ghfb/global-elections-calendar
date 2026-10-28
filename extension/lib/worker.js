// The worker's event routing (P131). Pure: Chrome's events are wired to these in background.js,
// so the order of calls can be tested without waiting for the events themselves.

export const ALARM_NAME = "elections-refresh";

// Each handler returns a promise, except `message`, which returns undefined at once for a
// message that is not one of ours (so the caller knows not to hold the reply channel open).
// `migratePins` and `editPin` never reject in production. On install, update and startup a failed
// or rejected migration is logged and never stops the alarm or the check (P140); a rejection on
// a `PINS` or `PIN_EDIT` message reaches the caller, and the listener in background.js turns it
// into an {ok: false} reply.
export function handlers({ runCheck, ensureAlarm, isDue, openHelp, migratePins, editPin }) {
  async function migrate() {
    try {
      const done = await migratePins();
      if (done && done.ok === false) console.error("pins", done.error);
    } catch (err) {
      console.error("pins", err);
    }
  }
  return {
    async installed(details) {
      if (details.reason === "install") {
        try {
          await openHelp();
        } catch (err) {
          console.error(err); // a help tab that cannot open must not stop the alarm or the check
        }
      }
      await migrate();
      await ensureAlarm();
      await runCheck();
    },
    async startup() {
      await migrate();
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
      if (typeof msg !== "object" || msg === null) return undefined;
      if (msg.type === "PINS") return migratePins();
      if (msg.type === "PIN_EDIT") return editPin({ op: msg.op, value: msg.value });
      if (msg.type !== "CHECK") return undefined;
      return (async () => {
        await ensureAlarm();
        if (msg.force || (await isDue())) return runCheck();
        return { ok: true, changed: false, skipped: true };
      })();
    },
  };
}
