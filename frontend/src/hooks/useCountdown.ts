import { useEffect, useState } from "react";

export type CountdownState = "counting" | "in_progress" | "finished";

export interface CountdownResult {
  days: string;
  hours: string;
  minutes: string;
  seconds: string;
  state: CountdownState;
}

/**
 * Calculates UTC epoch milliseconds for a local datetime in a specified IANA timezone.
 */
function getTargetUtcMillis(dateStr: string, timeStr: string, timeZone: string): number {
  try {
    const [year, month, day] = dateStr.split("-").map(Number);
    const [hours, minutes] = timeStr.split(":").map(Number);

    // Initial guess as UTC
    const utcGuess = new Date(Date.UTC(year, month - 1, day, hours, minutes, 0));

    const dtf = new Intl.DateTimeFormat("en-US", {
      timeZone,
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "numeric",
      minute: "numeric",
      second: "numeric",
      hour12: false,
    });

    const parts = dtf.formatToParts(utcGuess);
    const p: Record<string, number> = {};
    for (const part of parts) {
      if (part.type !== "literal") {
        p[part.type] = Number(part.value);
      }
    }

    const asLocalInTz = Date.UTC(
      p.year,
      p.month - 1,
      p.day,
      p.hour === 24 ? 0 : p.hour,
      p.minute,
      p.second,
    );
    const offset = asLocalInTz - utcGuess.getTime();
    return utcGuess.getTime() - offset;
  } catch {
    // Fallback if timezone is unparseable
    return new Date(`${dateStr}T${timeStr}:00`).getTime();
  }
}

export function useCountdown(
  eventDate: string,
  eventTime: string,
  eventTimezone: string,
): CountdownResult {
  const [result, setResult] = useState<CountdownResult>({
    days: "00",
    hours: "00",
    minutes: "00",
    seconds: "00",
    state: "counting",
  });

  useEffect(() => {
    if (!eventDate || !eventTime) return;

    const targetTime = getTargetUtcMillis(
      eventDate,
      eventTime,
      eventTimezone || "America/Bogota",
    );

    // Typical party duration window: 6 hours
    const eventDurationMs = 6 * 60 * 60 * 1000;

    function update() {
      const now = Date.now();
      const diff = targetTime - now;

      if (diff > 0) {
        const totalSeconds = Math.floor(diff / 1000);
        const days = Math.floor(totalSeconds / (3600 * 24));
        const hours = Math.floor((totalSeconds % (3600 * 24)) / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;

        setResult({
          days: String(days).padStart(2, "0"),
          hours: String(hours).padStart(2, "0"),
          minutes: String(minutes).padStart(2, "0"),
          seconds: String(seconds).padStart(2, "0"),
          state: "counting",
        });
      } else if (Math.abs(diff) < eventDurationMs) {
        setResult({
          days: "00",
          hours: "00",
          minutes: "00",
          seconds: "00",
          state: "in_progress",
        });
      } else {
        setResult({
          days: "00",
          hours: "00",
          minutes: "00",
          seconds: "00",
          state: "finished",
        });
      }
    }

    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [eventDate, eventTime, eventTimezone]);

  return result;
}
