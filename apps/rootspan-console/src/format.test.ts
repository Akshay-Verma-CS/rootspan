import { describe, expect, it } from "vitest";

import { percent, ratio, shortId } from "./format";

describe("incident formatters", () => {
  it("renders bounded operational values", () => {
    expect(percent(0.923)).toBe("92%");
    expect(ratio(17.2)).toBe("17×");
    expect(ratio(2.14)).toBe("2.1×");
    expect(shortId("12345678-abcd")).toBe("12345678");
  });
});
