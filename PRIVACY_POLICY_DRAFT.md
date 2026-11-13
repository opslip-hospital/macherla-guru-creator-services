# Privacy Policy — DRAFT FOR OWNER REVIEW

**Do not publish this draft as-is.** Before Google OAuth verification or real customer onboarding, the service owner must fill every bracketed field, confirm the actual data-retention practices and hosting regions, and obtain appropriate legal review.

- **Service/operator:** [Legal name of the person or business operating Macherla Guru Creator Services]
- **Contact:** [Public support/privacy email]
- **Business address/jurisdiction:** [Business address and applicable jurisdiction]
- **Effective date:** [Date]

## 1. Information the service handles

Depending on the features a customer uses, the service may process:

- Account details such as email address, display name, authentication identifiers, and workspace membership.
- YouTube channel details such as channel ID/title, granted OAuth scopes, recent video information, channel statistics, and YouTube Analytics metrics when authorized.
- OAuth refresh tokens, encrypted before storage and used only by the service's server-side YouTube integration.
- Video files customers upload to the service's private video-intake storage.
- AI-generated or customer-edited titles, descriptions, tags, hashtags, captions, keywords, and category metadata; customer-entered Content Studio topics/instructions; and selected channel metrics used for Growth Doctor suggestions.
- Support messages, workspace/billing-status records, security events, and audit logs.

The service does not collect payment-card details and does not process card payments or automatic charges.

## 2. How information is used

Information is used to operate customer workspaces, authenticate users, connect the customer's YouTube channel, show channel analytics, store video uploads privately, provide customer support, secure the service, and maintain administrative/audit records.

YouTube uploads are initially made **Private**. A video is made Public or scheduled only after the authenticated customer chooses the corresponding Publish or Schedule action.

## 3. Google YouTube API data

When a customer connects a YouTube channel, the service requests the YouTube permissions shown on Google's consent screen. The service uses the resulting authorization only to provide the channel connection, upload, customer-controlled publish/schedule, and analytics features the customer requests.

The service does not sell Google user data or use it for unrelated advertising. Google API data is handled in accordance with the applicable Google API Services User Data Policy and Limited Use requirements. Customers can disconnect a YouTube channel inside the service; this marks the connection revoked and clears the stored encrypted refresh token and granted scopes. Customers may also revoke the app's Google access from their Google Account security settings. Disconnecting does not cancel videos or schedules already held by YouTube. Historical channel identity and audit records may remain subject to the retention schedule; deletion requests for those records can be sent to [Public support/privacy email].

## 4. Gemini video analysis, text generation, and customer consent

AI video SEO is optional. The service sends a customer's video to the Google Gemini API only after the customer gives explicit per-video consent in the app. Content Studio topics/instructions and selected YouTube channel metrics are sent to Gemini only after a separate explicit text-generation consent in the app.

The current Gemini API **Free Tier** may use submitted prompts, responses, and files (including videos) to improve Google products. The service displays this notice before analysis. Google's Paid Tier has different data-use terms and states that submitted content is not used to improve Google products. The service owner must verify the active billing tier and Google's current terms before making any privacy promise.

Temporary Gemini Files API uploads are deleted on a best-effort basis after analysis. This does not override Google's applicable data-use, safety-monitoring, or retention terms.

## 5. Service providers and sharing

The service uses third-party infrastructure providers to operate its features, including:

- Supabase for authentication, database, private video storage, and server-side functions.
- Google YouTube APIs for channel access, uploads, publishing/scheduling, and analytics.
- Google Gemini API for video analysis when the customer consents.
- Streamlit hosting for the customer web application.

[Owner: confirm the actual providers, regions, contracts, and any additional subprocessors before publication.]

The service does not sell customer video files or Google user data. Data is shared with the providers above only as needed to deliver the requested service, protect the service, or comply with law.

## 6. Storage, security, and retention

Customer video intake storage is private and access is tenant-scoped. Customer workspace data is protected by database row-level security and server-side ownership checks. YouTube refresh tokens are encrypted before storage.

The owner must confirm and publish a specific retention schedule for source videos, generated metadata, analytics snapshots, support tickets, and audit logs. Until that schedule is finalized, customers may request deletion or account closure by contacting [Public support/privacy email]. The owner must implement and follow a documented deletion process before production launch.

## 7. Customer choices and rights

Customers may disconnect or revoke Google access through their Google Account settings and may request access, correction, or deletion of service-held information by contacting [Public support/privacy email]. The owner must define response timelines and any legal exceptions that apply in the service's operating jurisdiction.

## 8. Children and eligibility

[Owner: specify minimum user age and whether the service is intended for business/creator accounts only. Do not publish until this section is confirmed.]

## 9. Changes and contact

The owner may update this policy when the service, providers, data practices, or applicable law changes. Material changes should be communicated to customers.

Privacy questions and requests: **[Public support/privacy email]**.

## Owner publication checklist

- [ ] Fill legal operator name, address, jurisdiction, support/privacy email, and effective date.
- [ ] Confirm Gemini API Free/Paid tier and accurately describe Google data use.
- [ ] Confirm Supabase, Streamlit, and Google data regions and provider terms.
- [ ] Set and implement a retention/deletion schedule, including uploaded source videos and OAuth tokens.
- [ ] Confirm minimum age, customer rights process, and legal jurisdiction.
- [ ] Obtain legal review and publish on a public page under the verified custom domain.
