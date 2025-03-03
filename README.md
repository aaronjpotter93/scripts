# My Personal Helper Terminal Scripts

### TO DO: 
- [ ] Add Summaries for New Scripts:
```
.
├── cleanup
├── figme
├── obsidian
├── pkmg
├── restore
├── scrape
└── week50
```

- [ ] Create Scripts for:
```
.
├── new
├── run (maybe run runs should be added here from ~/Documents/env-profiles/dev  ?)
```

### ec2

> Summary: Automates SSH access to AWS EC2 instances by storing key paths and instance details, eliminating the need to manually enter them each time.

> TO DO: Make more secure. Involve age and sops

### opn

> Simplifies opening scripts in Visual Studio Code by allowing you to provide just the script name, reducing the need to type full paths.

> TO DO: maybe split the functionality of opn's create new scripts options to a new program because it feels weird to use opn to create new scripts when opn is just meant to speed up editing the scripts that have already been created, maybe make a new program called new that adds scripts to the path and collection as well as makes them executable. Also new should add a summary of the script to the readme (maybe run an api call on an llm to sumarize the script for you)

### treebat

> Summary: Merges the functionality of the `tree` and `bat` commands, useful for exploring directory structures and viewing file contents simultaneously.

> TO DO: Need to add a check before calling bat in the case that its a very large file (maybe limit to a certain number of lines to print) or a file type that wouln't be human readable, or to not recursively dive into library directories. 

### budget

> Generates a budget based on income and savings priorities, helping to plan spending scenarios over a year for financial sustainability.

<!-- ## 🔄 Restoration

This project uses the standard cleanup process. To restore dependencies: -->

