"use client";

import {
  AUTH_INTENT_KEY,
  DECLINED_EMAILS_KEY,
  WELCOME_BACK_KEY,
  addDeclinedEmail,
  parseIntent,
  removeDeclinedEmail,
  type AuthIntent,
} from "./auth-flow";

function session(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

function local(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function saveIntent(intent: AuthIntent) {
  session()?.setItem(AUTH_INTENT_KEY, intent);
}

export function readIntent(): AuthIntent {
  return parseIntent(session()?.getItem(AUTH_INTENT_KEY));
}

export function clearIntent() {
  session()?.removeItem(AUTH_INTENT_KEY);
}

export function flagWelcomeBack() {
  session()?.setItem(WELCOME_BACK_KEY, "1");
}

export function consumeWelcomeBack(): boolean {
  const store = session();
  if (!store || store.getItem(WELCOME_BACK_KEY) !== "1") return false;
  store.removeItem(WELCOME_BACK_KEY);
  return true;
}

function readDeclined(): string[] {
  try {
    const parsed: unknown = JSON.parse(local()?.getItem(DECLINED_EMAILS_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

export function isDeclinedEmail(email: string): boolean {
  return readDeclined().includes(email.trim().toLowerCase());
}

export function markDeclinedEmail(email: string) {
  local()?.setItem(DECLINED_EMAILS_KEY, JSON.stringify(addDeclinedEmail(readDeclined(), email)));
}

export function clearDeclinedEmail(email: string) {
  local()?.setItem(DECLINED_EMAILS_KEY, JSON.stringify(removeDeclinedEmail(readDeclined(), email)));
}
