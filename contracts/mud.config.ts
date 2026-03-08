import { defineWorld } from "@latticexyz/world";

export default defineWorld({
  namespace: "watcher",
  tables: {
    WatcherSubscriptions: {
      schema: {
        subscriber: "address",
        tier: "uint8",
        expiresAt: "uint256",
      },
      key: ["subscriber"],
    },
  },
});
