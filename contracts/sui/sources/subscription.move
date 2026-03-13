/// WatchTower Subscription — on-chain tier access via SUI or LUX payment.
///
/// Architecture:
///   - SubscriptionConfig (shared): mutable prices, updated by admin via oracle
///   - SubscriptionRegistry (shared): tracks all subscriptions + revenue
///   - SubscriptionCap (owned): proof of subscription held by user's wallet
///
/// Prices are set in MIST (1 SUI = 1_000_000_000 MIST).
/// Backend oracle pushes price updates via update_prices() when SUI/USD moves.
///
/// Tier pricing (USD source of truth, SUI equivalent at deploy):
///   Scout (1):     ~$4.99/wk
///   Oracle (2):    ~$9.99/wk
///   Spymaster (3): ~$19.99/wk
#[allow(lint(self_transfer))]
module watchtower::subscription {
    use sui::coin::{Self, Coin};
    use sui::event;
    use sui::sui::SUI;
    use sui::table::{Self, Table};

    // ===== Error codes =====
    const EInvalidTier: u64 = 1;
    const EInsufficientPayment: u64 = 2;
    const EInvalidDuration: u64 = 3;


    // ===== Tier constants =====
    const TIER_SCOUT: u8 = 1;
    const TIER_ORACLE: u8 = 2;
    const TIER_SPYMASTER: u8 = 3;

    // ===== Duration =====
    const WEEK_MS: u64 = 604_800_000; // 7 days in ms

    // ===== Structs =====

    /// Admin capability — held by WatchTower deployer.
    public struct AdminCap has key, store {
        id: UID,
    }

    /// Shared pricing config. Prices mutable via update_prices().
    /// Separate from registry so price reads don't contend with writes.
    public struct SubscriptionConfig has key {
        id: UID,
        price_scout: u64,     // MIST per week
        price_oracle: u64,
        price_spymaster: u64,
    }

    /// Shared subscription registry. Tracks active subs + collects revenue.
    public struct SubscriptionRegistry has key {
        id: UID,
        subscriptions: Table<address, SubscriptionRecord>,
        total_subscriptions: u64,
        total_revenue_mist: u64,
        treasury: address,
    }

    /// On-chain subscription record for a wallet (in registry).
    public struct SubscriptionRecord has store, copy, drop {
        tier: u8,
        expires_at_ms: u64,
        purchased_at_ms: u64,
        total_paid_mist: u64,
    }

    /// Owned by the subscriber. Proves active subscription.
    /// Lives in user's wallet — verifiable without backend.
    public struct SubscriptionCap has key, store {
        id: UID,
        tier: u8,
        owner: address,
        expires_at_ms: u64,
    }

    // ===== Events =====

    /// Emitted on every subscription purchase. Poller indexes this.
    public struct SubscriptionPurchased has copy, drop {
        subscriber: address,
        tier: u8,
        expires_at_ms: u64,
        paid_mist: u64,
    }

    /// Emitted on renewal. Poller indexes this.
    public struct SubscriptionRenewed has copy, drop {
        subscriber: address,
        tier: u8,
        new_expires_at_ms: u64,
        paid_mist: u64,
    }

    /// Emitted when admin grants a comp subscription.
    public struct SubscriptionGranted has copy, drop {
        subscriber: address,
        tier: u8,
        expires_at_ms: u64,
        granted_by: address,
    }

    /// Emitted when admin credits a subscription after off-chain LUX payment.
    public struct LuxPaymentCredited has copy, drop {
        subscriber: address,
        tier: u8,
        expires_at_ms: u64,
    }

    /// Emitted when prices are updated by admin.
    public struct PricesUpdated has copy, drop {
        price_scout: u64,
        price_oracle: u64,
        price_spymaster: u64,
    }

    // ===== Init =====

    fun init(ctx: &mut TxContext) {
        let sender = ctx.sender();

        transfer::transfer(
            AdminCap { id: object::new(ctx) },
            sender,
        );

        // Default prices at ~$3.42/SUI:
        // Scout=$4.99 → 1.46 SUI, Oracle=$9.99 → 2.92 SUI, Spymaster=$19.99 → 5.84 SUI
        transfer::share_object(
            SubscriptionConfig {
                id: object::new(ctx),
                price_scout: 1_460_000_000,
                price_oracle: 2_920_000_000,
                price_spymaster: 5_840_000_000,
            },
        );

        transfer::share_object(
            SubscriptionRegistry {
                id: object::new(ctx),
                subscriptions: table::new(ctx),
                total_subscriptions: 0,
                total_revenue_mist: 0,
                treasury: sender,
            },
        );
    }

    // ===== Public: Subscribe with SUI =====

    /// Purchase a subscription tier with SUI.
    /// Reads price from SubscriptionConfig (dynamic).
    /// Extends if already subscribed. Mints SubscriptionCap.
    public fun subscribe(
        config: &SubscriptionConfig,
        registry: &mut SubscriptionRegistry,
        tier: u8,
        mut payment: Coin<SUI>,
        clock: &sui::clock::Clock,
        ctx: &mut TxContext,
    ) {
        assert!(tier >= TIER_SCOUT && tier <= TIER_SPYMASTER, EInvalidTier);

        let required = config_price(config, tier);
        let paid = coin::value(&payment);
        assert!(paid >= required, EInsufficientPayment);

        // Split exact amount to treasury, refund overpayment
        let treasury_coin = coin::split(&mut payment, required, ctx);
        transfer::public_transfer(treasury_coin, registry.treasury);

        if (coin::value(&payment) > 0) {
            transfer::public_transfer(payment, ctx.sender());
        } else {
            coin::destroy_zero(payment);
        };

        // Calculate expiry
        let now_ms = sui::clock::timestamp_ms(clock);
        let subscriber = ctx.sender();

        let expires_at_ms = if (registry.subscriptions.contains(subscriber)) {
            let existing = registry.subscriptions.borrow(subscriber);
            let base = if (existing.expires_at_ms > now_ms) {
                existing.expires_at_ms
            } else {
                now_ms
            };
            base + WEEK_MS
        } else {
            now_ms + WEEK_MS
        };

        // Upsert registry record
        if (registry.subscriptions.contains(subscriber)) {
            let existing = registry.subscriptions.borrow_mut(subscriber);
            existing.tier = if (tier > existing.tier) { tier } else { existing.tier };
            existing.expires_at_ms = expires_at_ms;
            existing.purchased_at_ms = now_ms;
            existing.total_paid_mist = existing.total_paid_mist + required;
        } else {
            registry.subscriptions.add(subscriber, SubscriptionRecord {
                tier,
                expires_at_ms,
                purchased_at_ms: now_ms,
                total_paid_mist: required,
            });
            registry.total_subscriptions = registry.total_subscriptions + 1;
        };

        registry.total_revenue_mist = registry.total_revenue_mist + required;

        // Mint SubscriptionCap (owned proof)
        let cap = SubscriptionCap {
            id: object::new(ctx),
            tier,
            owner: subscriber,
            expires_at_ms,
        };
        transfer::transfer(cap, subscriber);

        event::emit(SubscriptionPurchased {
            subscriber,
            tier,
            expires_at_ms,
            paid_mist: required,
        });
    }

    // ===== Public: Renew =====

    /// Renew an existing subscription. Extends expiry by one week.
    /// Extends from current expiry (not from now — rewards early renewal).
    public fun renew(
        config: &SubscriptionConfig,
        registry: &mut SubscriptionRegistry,
        cap: &mut SubscriptionCap,
        mut payment: Coin<SUI>,
        clock: &sui::clock::Clock,
        ctx: &mut TxContext,
    ) {
        let required = config_price(config, cap.tier);
        let paid = coin::value(&payment);
        assert!(paid >= required, EInsufficientPayment);

        let treasury_coin = coin::split(&mut payment, required, ctx);
        transfer::public_transfer(treasury_coin, registry.treasury);

        if (coin::value(&payment) > 0) {
            transfer::public_transfer(payment, ctx.sender());
        } else {
            coin::destroy_zero(payment);
        };

        let now_ms = sui::clock::timestamp_ms(clock);

        // Extend from current expiry (rewards early renewal)
        let base = if (cap.expires_at_ms > now_ms) {
            cap.expires_at_ms
        } else {
            now_ms
        };
        let new_expiry = base + WEEK_MS;
        cap.expires_at_ms = new_expiry;

        // Update registry
        let subscriber = cap.owner;
        if (registry.subscriptions.contains(subscriber)) {
            let existing = registry.subscriptions.borrow_mut(subscriber);
            existing.expires_at_ms = new_expiry;
            existing.purchased_at_ms = now_ms;
            existing.total_paid_mist = existing.total_paid_mist + required;
        };

        registry.total_revenue_mist = registry.total_revenue_mist + required;

        event::emit(SubscriptionRenewed {
            subscriber,
            tier: cap.tier,
            new_expires_at_ms: new_expiry,
            paid_mist: required,
        });
    }

    // ===== Admin: Update prices =====

    /// Update prices after SUI/USD movement. Called by backend oracle.
    public fun update_prices(
        _cap: &AdminCap,
        config: &mut SubscriptionConfig,
        price_scout: u64,
        price_oracle: u64,
        price_spymaster: u64,
    ) {
        config.price_scout = price_scout;
        config.price_oracle = price_oracle;
        config.price_spymaster = price_spymaster;

        event::emit(PricesUpdated {
            price_scout,
            price_oracle,
            price_spymaster,
        });
    }

    // ===== Admin: Grant comp subscription =====

    /// Grant a free subscription (hackathon prizes, partnerships, etc).
    public fun grant_subscription(
        _cap: &AdminCap,
        registry: &mut SubscriptionRegistry,
        subscriber: address,
        tier: u8,
        duration_days: u64,
        clock: &sui::clock::Clock,
        ctx: &mut TxContext,
    ) {
        assert!(tier >= TIER_SCOUT && tier <= TIER_SPYMASTER, EInvalidTier);
        assert!(duration_days > 0 && duration_days <= 365, EInvalidDuration);

        let now_ms = sui::clock::timestamp_ms(clock);
        let duration_ms = duration_days * 86_400_000;

        let expires_at_ms = if (registry.subscriptions.contains(subscriber)) {
            let existing = registry.subscriptions.borrow(subscriber);
            let base = if (existing.expires_at_ms > now_ms) {
                existing.expires_at_ms
            } else {
                now_ms
            };
            base + duration_ms
        } else {
            now_ms + duration_ms
        };

        if (registry.subscriptions.contains(subscriber)) {
            let existing = registry.subscriptions.borrow_mut(subscriber);
            existing.tier = if (tier > existing.tier) { tier } else { existing.tier };
            existing.expires_at_ms = expires_at_ms;
            existing.purchased_at_ms = now_ms;
        } else {
            registry.subscriptions.add(subscriber, SubscriptionRecord {
                tier,
                expires_at_ms,
                purchased_at_ms: now_ms,
                total_paid_mist: 0,
            });
            registry.total_subscriptions = registry.total_subscriptions + 1;
        };

        // Mint SubscriptionCap for the subscriber
        let cap = SubscriptionCap {
            id: object::new(ctx),
            tier,
            owner: subscriber,
            expires_at_ms,
        };
        transfer::transfer(cap, subscriber);

        event::emit(SubscriptionGranted {
            subscriber,
            tier,
            expires_at_ms,
            granted_by: ctx.sender(),
        });
    }

    // ===== Admin: Credit LUX payment =====

    /// Admin credits a subscription after verifying LUX payment off-chain.
    public fun credit_lux_payment(
        _cap: &AdminCap,
        registry: &mut SubscriptionRegistry,
        subscriber: address,
        tier: u8,
        clock: &sui::clock::Clock,
        ctx: &mut TxContext,
    ) {
        assert!(tier >= TIER_SCOUT && tier <= TIER_SPYMASTER, EInvalidTier);

        let now_ms = sui::clock::timestamp_ms(clock);

        let expires_at_ms = if (registry.subscriptions.contains(subscriber)) {
            let existing = registry.subscriptions.borrow(subscriber);
            let base = if (existing.expires_at_ms > now_ms) {
                existing.expires_at_ms
            } else {
                now_ms
            };
            base + WEEK_MS
        } else {
            now_ms + WEEK_MS
        };

        if (registry.subscriptions.contains(subscriber)) {
            let existing = registry.subscriptions.borrow_mut(subscriber);
            existing.tier = if (tier > existing.tier) { tier } else { existing.tier };
            existing.expires_at_ms = expires_at_ms;
            existing.purchased_at_ms = now_ms;
        } else {
            registry.subscriptions.add(subscriber, SubscriptionRecord {
                tier,
                expires_at_ms,
                purchased_at_ms: now_ms,
                total_paid_mist: 0,
            });
            registry.total_subscriptions = registry.total_subscriptions + 1;
        };

        // Mint SubscriptionCap
        let cap = SubscriptionCap {
            id: object::new(ctx),
            tier,
            owner: subscriber,
            expires_at_ms,
        };
        transfer::transfer(cap, subscriber);

        event::emit(LuxPaymentCredited {
            subscriber,
            tier,
            expires_at_ms,
        });
    }

    // ===== Admin: Update treasury =====

    public fun update_treasury(
        _cap: &AdminCap,
        registry: &mut SubscriptionRegistry,
        new_treasury: address,
    ) {
        registry.treasury = new_treasury;
    }

    // ===== Public reads =====

    /// Check if a wallet has an active subscription at or above a given tier.
    public fun has_tier(
        registry: &SubscriptionRegistry,
        subscriber: address,
        min_tier: u8,
        clock: &sui::clock::Clock,
    ): bool {
        if (!registry.subscriptions.contains(subscriber)) {
            return false
        };
        let record = registry.subscriptions.borrow(subscriber);
        let now_ms = sui::clock::timestamp_ms(clock);
        record.tier >= min_tier && record.expires_at_ms > now_ms
    }

    /// Check if a SubscriptionCap is still active.
    public fun is_active(cap: &SubscriptionCap, clock: &sui::clock::Clock): bool {
        sui::clock::timestamp_ms(clock) < cap.expires_at_ms
    }

    /// Get price for a tier from config (in MIST).
    public fun config_price(config: &SubscriptionConfig, tier: u8): u64 {
        if (tier == TIER_SCOUT) { config.price_scout }
        else if (tier == TIER_ORACLE) { config.price_oracle }
        else if (tier == TIER_SPYMASTER) { config.price_spymaster }
        else { abort EInvalidTier }
    }

    /// Get subscription record for a wallet.
    public fun get_subscription(
        registry: &SubscriptionRegistry,
        subscriber: address,
    ): &SubscriptionRecord {
        assert!(registry.subscriptions.contains(subscriber), EInvalidTier);
        registry.subscriptions.borrow(subscriber)
    }

    /// Accessors
    public fun tier(record: &SubscriptionRecord): u8 { record.tier }
    public fun expires_at_ms(record: &SubscriptionRecord): u64 { record.expires_at_ms }
    public fun total_paid_mist(record: &SubscriptionRecord): u64 { record.total_paid_mist }
    public fun total_subscriptions(registry: &SubscriptionRegistry): u64 {
        registry.total_subscriptions
    }
    public fun total_revenue_mist(registry: &SubscriptionRegistry): u64 {
        registry.total_revenue_mist
    }
    public fun cap_tier(cap: &SubscriptionCap): u8 { cap.tier }
    public fun cap_expires_at(cap: &SubscriptionCap): u64 { cap.expires_at_ms }

    // ===== Test-only =====

    #[test_only]
    public fun init_for_testing(ctx: &mut TxContext) {
        init(ctx);
    }
}
