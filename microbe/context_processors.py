from microbe.utils import microbe_config


def apis(request):
    return {
        "ENA_BROWSER_URL": microbe_config.ena.browser_url,
        "MGNIFY_WEB_URL": microbe_config.mgnify.web_url,
        "MGNIFY_API_URL": microbe_config.mgnify.api_root,
        "METABOLIGHTS_WEB_URL": microbe_config.metabolights.web_url,
        "METABOLIGHTS_API_URL": microbe_config.metabolights.api_root,
        "DOCS_URL": microbe_config.docs.docs_url,
        "PORTAL_DOI": microbe_config.docs.portal_doi,
    }
