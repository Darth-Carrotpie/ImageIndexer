# Owner directions: public data and ordinary Git

> Source: Owner messages in the package release conversation
> Collected: 2026-10-12
> Published: 2026-10-12

## License decision

Instead of chosing licence, you can right away note it in the readme and add relevant licence files: MIT license.

## Public data boundary clarification

787KB feels that it does not contain the index or the DB. Will cloning the repo work for our deployment purposes? Our goal is to have a repository of the generated data and scripts, which can be public and at the same time to publicise an approach how to index and create an agent-assisted image-picking tool. The db itself would serve as an example for others, and a deployable index db (with code and source for later improvements and expansion) for ourselves. There are two reasons we are splitting the images themselves to a private NextCloud storage: 1. it is large; 2. we do not own re-sale licence or free re-distribution. We can only use the images in our own projects, which themselves can be products, but not the images themselves. So we keep exact images private.
The github repository should be easily clonable and later-versionable for our own use.

## Implementation authorization

Lets stay with ordinary github storage.
the intended boundary outline is correct.
Perform the recommended steps and write me which steps I should take manually. Github repo: [https://github.com/Darth-Carrotpie/ImageIndexer](https://github.com/Darth-Carrotpie/ImageIndexer)
