import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it } from "vitest";

import { session } from "./session";
import { bindQueryCacheToSession } from "./sessionCache";

const token = (sub: string) => `x.${btoa(JSON.stringify({ sub })).replaceAll("=", "")}.y`;

describe("bindQueryCacheToSession", () => {
  let unbind = () => {};
  afterEach(() => {
    unbind();
    session.signOut();
  });

  it("czyści cache po wylogowaniu i przy zmianie konta, ale nie przy odświeżeniu tokena", () => {
    const qc = new QueryClient();
    unbind = bindQueryCacheToSession(qc);

    session.signIn(token("user-a"));
    qc.setQueryData(["weddings"], ["Wesele A"]);
    session.signIn(token("user-a")); // odświeżenie tokena tego samego konta
    expect(qc.getQueryData(["weddings"])).toEqual(["Wesele A"]);

    session.signOut();
    expect(qc.getQueryData(["weddings"])).toBeUndefined();

    session.signIn(token("user-a"));
    qc.setQueryData(["weddings"], ["Wesele A"]);
    session.signIn(token("user-b")); // inne konto bez wylogowania
    expect(qc.getQueryData(["weddings"])).toBeUndefined();
  });
});
