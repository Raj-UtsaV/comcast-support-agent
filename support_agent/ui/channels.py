def support_channels(config):
    """Only administrator-configured HTTPS destinations become clickable links."""
    return [item for item in config.get("customer_support", {}).get("channels", [])
            if isinstance(item.get("url"), str) and item["url"].startswith("https://")]
