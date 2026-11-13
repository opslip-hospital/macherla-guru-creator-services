import streamlit as st

st.set_page_config(page_title="Privacy Policy — Macherla Guru Creator Services", page_icon="🔒", layout="centered")
st.title("Privacy Policy")
st.caption("Macherla Guru Creator Services • Effective 13 November 2026")
st.warning("This policy draft describes the current application design. The service operator must review and confirm the support contact, retention periods, and deletion procedures before public OAuth verification or customer onboarding.")

st.markdown("""
## 1. Information we process
When you create an account or use the service, we process your name, email address, account and workspace identifiers, support messages, and service activity needed to operate your workspace.

If you connect a YouTube channel, we receive the channel ID and title, the permissions (OAuth scopes) you grant, and the channel/video information needed to show your channel dashboard and analytics. Depending on the permissions granted, this can include subscriber, view, video, likes, comments, and YouTube Analytics metrics.

When you upload a video for AI SEO, the video file is stored in a private service bucket and transmitted to Google's Gemini API for video analysis and metadata generation. The resulting title suggestions, description, tags, hashtags, captions, keywords, and category are stored with your workspace. A temporary Gemini file is deleted on a best-effort basis after processing; if provider-side deletion fails, Google's applicable API retention terms govern that copy.

## 2. How we use information
We use information to:
- authenticate users and provide isolated customer workspaces;
- connect the YouTube channel you authorize;
- display channel and video performance information;
- analyze video files and prepare AI-generated SEO/content drafts;
- upload videos as Private and carry out Publish now or Schedule only after the workspace owner explicitly chooses that action;
- respond to support requests, protect the service, and maintain audit records.

AI-generated content is a draft for you to review. You remain responsible for checking it before upload or publication.

## 3. Google and YouTube access
Connecting YouTube is optional. Google OAuth grants only the scopes shown on Google's consent screen. The service stores the YouTube refresh token encrypted with AES-GCM in a non-public database schema. The token is used by server-side functions to perform the YouTube actions you request; it is not displayed in the customer dashboard.

You can revoke the service's access from your Google Account security settings. Revoking access may stop channel refresh, uploads, publishing, or scheduling until you reconnect.

The service uses YouTube API Services. Your use of YouTube remains subject to Google's and YouTube's terms and policies. You can review Google's privacy policy at https://policies.google.com/privacy.

## 4. Service providers
The service uses Supabase for authentication, database, private file storage, and server-side functions; Streamlit Community Cloud to host the customer application; and Google APIs, including YouTube and Gemini, for channel operations and AI video analysis. These providers process information as needed to provide their services and under their applicable terms.

We do not sell customer personal information. Access to customer records is restricted by workspace-level database policies. Authorized service administrators may access limited records when needed for support, security, or service administration.

## 5. Storage, security, and retention
Uploaded intake files are stored in a private bucket. Customer records are isolated by workspace policies. YouTube refresh tokens are encrypted before storage. No security measure can guarantee absolute security.

We retain account, workspace, metadata, analytics, support, and audit information for as long as reasonably needed to operate the service, meet security and legal requirements, and resolve disputes. Uploaded video files may remain in private storage until removed by the service operator. To request access, correction, or deletion, submit a request through the in-app Support area. Some records may remain in backups or audit logs where retention is necessary.

## 6. Payments
The current dashboard records plan and subscription status for administration only. It does not collect card details, process payments, or make automatic charges.

## 7. Your choices and responsibilities
You may disconnect YouTube access through your Google Account. You may contact support to request account or data changes. Do not upload videos unless you have the necessary rights and permissions. Do not submit confidential or sensitive information that is not needed for the service.

## 8. Children
The service is intended for people who are legally able to enter into a service agreement. Do not create an account on behalf of a child without appropriate legal authority and consent.

## 9. Changes and contact
We may update this policy when the service changes. The current version will be published on this page. For privacy questions or requests, use the in-app Support area. Before public launch, the operator must add and maintain a public support contact on the verified service website and Google OAuth consent screen.

## 10. YouTube API Services disclosure
The service's use and transfer to any other app of information received from Google APIs will adhere to the Google API Services User Data Policy, including the Limited Use requirements.
""")
