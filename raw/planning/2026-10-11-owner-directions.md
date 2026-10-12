# Owner directions for the initial release and public project

> Source: Owner messages in this workspace conversation
> Collected: 2026-10-11
> Published: Unknown

Selected messages are reproduced verbatim. They establish intent, not evidence
that a future feature has been implemented or a public release authorized.

## Search acceptance and alternative descriptions

Before adjusments let's lower the requirement from 90% to 80%, for our needs it would be enough.
I've reviewed the FAILURE DIAGNOSIS report, most cases seem that they are not hard mismatch, instead more like alternative descriptions of what is in the image. In such case, it would might be a good decision to keep both synonimical alternatives, or perhaps even more. The later chosing for pickup will be not simply matched, but also ingested by LLM from the description as well, therefore a few alternatives can be usefull to describe what is in the image, especially when most of the icons are partially abstract or schematic. Keeping this in mind, propose next steps and how to finalize this package for initial release to test it in the wild.

## Automated finishing

No independent manual reviewers. Everything should be automated.
Update the plan by adding concrete finishing steps, then perform those steps. I we need to rebuild 6k icons descriptions or something else in the database, stop and prompt me before the rebuild - I will then select an appropriate model (or if you use API, then you can just select GPT-6 Sol-High again and continue without interuption. However, if a change here is needed, you should stop, then I will do swap, do the run of all icons, then I will swap back.

## Private image distribution

Good, finally, walk me through a release process. We have a private NextCloud instance to store the static images. Our package therefore should be split in two:
One or a few zips of all of the icons (i.e. 1GB size each), and a no-icon build  with a script which downloads the icons from the cloud url which is behind a password. Prepare these packages, zips, and the script. I will later point the script to the NextCloud links and add the password.

## Public project and local wiki

Suggest best distribution flow for the no-icon package. Should we init git in this project?
After testing, if it works, I prefer a publig git repo, with presentation of the core idea and approach, as well as a plan for implementation, or ingestiong of the new packages. For this purpose init a wiki here based on all that has been achieved. Include the principles, tech stack and purpose inside the wiki.
