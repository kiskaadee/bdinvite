import { useEffect, useState } from "react";
import { submitRsvp } from "../api/client";

const SESSION_STORAGE_KEY = "bdinvite:rsvp-submitted";

export type RsvpFormState = "idle" | "submitting" | "success" | "duplicate" | "error";

export interface FormErrors {
  name?: string;
  phone?: string;
  email?: string;
}

export function useRsvpForm() {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [confirmedName, setConfirmedName] = useState("");

  const [formState, setFormState] = useState<RsvpFormState>("idle");
  const [errors, setErrors] = useState<FormErrors>({});

  // Check sessionStorage on mount for existing submission in this session
  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed?.name) {
          setConfirmedName(parsed.name);
          setFormState("success");
        }
      }
    } catch {
      // Ignore sessionStorage read errors
    }
  }, []);

  function validate(): boolean {
    const newErrors: FormErrors = {};

    const cleanName = name.trim();
    if (!cleanName) {
      newErrors.name = "Por favor, ingresa tu nombre completo.";
    }

    // Colombian mobile format: 10 digits starting with 3, optionally +57
    const digits = phone.replace(/\D/g, "");
    let normalized = digits;
    if (normalized.startsWith("57") && normalized.length === 12) {
      normalized = normalized.slice(2);
    }

    if (normalized.length !== 10 || !normalized.startsWith("3")) {
      newErrors.phone =
        "Ingresa un número móvil válido de 10 dígitos (ej: 300 123 4567).";
    }

    if (email?.trim()) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email.trim())) {
        newErrors.email = "Ingresa un correo electrónico válido.";
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }

  async function submit() {
    if (!validate()) return;

    setFormState("submitting");

    // Clean phone
    let digits = phone.replace(/\D/g, "");
    if (digits.startsWith("57") && digits.length === 12) {
      digits = digits.slice(2);
    }

    const payload = {
      name: name.trim(),
      phone: digits,
      email: email.trim() || null,
    };

    const result = await submitRsvp(payload);

    if (result.result === "SUCCESS") {
      setConfirmedName(result.name);
      setFormState("success");
      try {
        sessionStorage.setItem(
          SESSION_STORAGE_KEY,
          JSON.stringify({ name: result.name, timestamp: Date.now() }),
        );
      } catch {
        // Ignore storage write issues
      }
    } else if (result.result === "DUPLICATE") {
      setFormState("duplicate");
    } else if (result.result === "VALIDATION_ERROR") {
      setFormState("idle");
      setErrors(result.errors);
    } else {
      setFormState("error");
    }
  }

  function retry() {
    setFormState("idle");
  }

  return {
    name,
    setName,
    phone,
    setPhone,
    email,
    setEmail,
    confirmedName,
    formState,
    errors,
    submit,
    retry,
  };
}
