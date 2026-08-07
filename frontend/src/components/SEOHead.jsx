import React from 'react';
import { Helmet } from 'react-helmet-async';

export default function SEOHead({
  title = "PolicyCrab - AI US Insurance Claims Engine",
  description = "AI-powered US health insurance claims engine. Evaluate eligibility, estimate costs, and draft appeals for denied claims.",
  canonicalUrl = "https://policycrab.tech",
  ogType = "website",
  jsonLd = null,
}) {
  const defaultImage = "https://policycrab.tech/og-image.png";

  return (
    <Helmet>
      <title>{title}</title>
      <meta name="description" content={description} />
      <link rel="canonical" href={canonicalUrl} />

      {/* Open Graph / Facebook */}
      <meta property="og:type" content={ogType} />
      <meta property="og:url" content={canonicalUrl} />
      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
      <meta property="og:image" content={defaultImage} />
      <meta property="og:site_name" content="PolicyCrab" />

      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:url" content={canonicalUrl} />
      <meta name="twitter:title" content={title} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={defaultImage} />

      {/* JSON-LD Structured Data */}
      {jsonLd && (
        <script type="application/ld+json">
          {JSON.stringify(jsonLd)}
        </script>
      )}
    </Helmet>
  );
}
