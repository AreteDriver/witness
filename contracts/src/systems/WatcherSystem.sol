// SPDX-License-Identifier: MIT
pragma solidity >=0.8.24;

import { System } from "@latticexyz/world/src/System.sol";
import { WatcherSubscriptions } from "../codegen/tables/WatcherSubscriptions.sol";

/// @title WatcherSystem — Subscription gating for WatchTower oracle services
/// @notice Players pay to access tiered intelligence: Scout, Oracle, Spymaster
/// @dev Deployed as a Smart Assembly; items exchanged via inventory system
contract WatcherSystem is System {
    // --- Tier constants ---
    uint8 public constant TIER_FREE = 0;
    uint8 public constant TIER_SCOUT = 1;
    uint8 public constant TIER_ORACLE = 2;
    uint8 public constant TIER_SPYMASTER = 3;

    // Subscription duration: 7 days per payment
    uint256 public constant SUBSCRIPTION_DURATION = 7 days;

    // --- Events ---
    event SubscriptionCreated(address indexed subscriber, uint8 tier, uint256 expiresAt);
    event SubscriptionRenewed(address indexed subscriber, uint8 tier, uint256 expiresAt);

    // --- Errors ---
    error InvalidTier(uint8 tier);

    /// @notice Subscribe to a Watcher tier. Called after item transfer.
    /// @param tier The subscription tier (1=Scout, 2=Oracle, 3=Spymaster)
    /// @dev In production, validate item transfer via inventory system.
    ///      For hackathon, we trust the caller and record the subscription.
    function subscribe(uint8 tier) public {
        if (tier < TIER_SCOUT || tier > TIER_SPYMASTER) {
            revert InvalidTier(tier);
        }

        address subscriber = _msgSender();
        uint256 currentExpiry = WatcherSubscriptions.getExpiresAt(subscriber);
        uint256 now_ = block.timestamp;

        uint256 newExpiry;
        if (currentExpiry > now_) {
            // Extend existing subscription
            newExpiry = currentExpiry + SUBSCRIPTION_DURATION;
            emit SubscriptionRenewed(subscriber, tier, newExpiry);
        } else {
            // New subscription
            newExpiry = now_ + SUBSCRIPTION_DURATION;
            emit SubscriptionCreated(subscriber, tier, newExpiry);
        }

        WatcherSubscriptions.set(subscriber, tier, newExpiry);
    }

    /// @notice Check if an address has active access at a given tier
    /// @param subscriber The wallet address to check
    /// @param requiredTier Minimum tier required
    /// @return hasAccess Whether the subscriber has active access
    function checkAccess(
        address subscriber,
        uint8 requiredTier
    ) public view returns (bool hasAccess) {
        uint8 tier = WatcherSubscriptions.getTier(subscriber);
        uint256 expiresAt = WatcherSubscriptions.getExpiresAt(subscriber);

        return tier >= requiredTier && expiresAt > block.timestamp;
    }

    /// @notice Get full subscription details for an address
    /// @param subscriber The wallet address to query
    /// @return tier Current tier (0 if none)
    /// @return expiresAt Expiry timestamp (0 if never subscribed)
    /// @return active Whether subscription is currently active
    function getSubscription(
        address subscriber
    ) public view returns (uint8 tier, uint256 expiresAt, bool active) {
        tier = WatcherSubscriptions.getTier(subscriber);
        expiresAt = WatcherSubscriptions.getExpiresAt(subscriber);
        active = tier > TIER_FREE && expiresAt > block.timestamp;
    }
}
