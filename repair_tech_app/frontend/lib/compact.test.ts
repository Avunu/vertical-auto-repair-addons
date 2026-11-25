import {expect, it} from "vitest";
import {compact} from "./compact";

it("drops undefined keys and keeps falsy values", () => {
  expect(compact({a: undefined, b: 0, c: "", d: null, e: "x"})).toEqual({
    b: 0,
    c: "",
    d: null,
    e: "x",
  });
});
