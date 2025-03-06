# My Personal Helper Terminal Scripts

[//]: # (Tree with anchor links - use HTML to preserve formatting)
<pre class="highlight"><code>.
├── <a href="#budget">budget</a>
├── <a href="#clean">clean</a>
├── <a href="#ec2">ec2</a>
├── <a href="#figme">figme</a>
├── <a href="#gitgo">gitgo</a>
├── <a href="#inv">inv</a>
├── <a href="#obsidian">obsidian</a>
├── <a href="#opn">opn</a>
├── <a href="#pkgs">pkgs</a>
├── <a href="#restore">restore</a>
├── <a href="#scrape">scrape</a>
├── <a href="#treebat">treebat</a>
└── <a href="#week50">week50</a>

# </span><a href="#todo">TO DO:</a>
---
<a href="#clean">clean</a>
<a href="#todo-ec2">ec2</a>
<a href="#restore">restore</a>
<a href="#todo-treebat">treebat</a>
---

</code></pre>

### Script Descriptions

#### budget
> Generates budget scenarios with income/savings projections and expense tracking for financial planning.

#### clean
> Automated system maintenance script that removes large files and libraries to optimize storage.

#### ec2
> Simplifies AWS EC2 instance access with stored SSH configurations for quick server connections.

#### figme
> Displays personalized ASCII art header using jp2a and Figlet for terminal customization.

#### gitgo
> Automates git add . commit and push for a couple high traffic projects

#### inv
> System inventory auditor tracking installed packages across Homebrew, Node.js, Python, and Go environments.

#### obsidian
> Obsidian vault manager automating markdown template generation with academic metadata.

#### opn
> Script workspace manager with VS Code integration and permission handling utilities.

#### pkgs
> Dependency scanner that analyzes project package manifests (npm, Maven) for installed components.

#### restore
> System restoration utility for recovering configurations and important files from backups.

#### scrape
> Web scraping tool for batch downloading PDF resources from educational websites.

#### treebat
> Enhanced directory visualizer with syntax highlighting and gitignore-aware filtering.

#### week50
> CS50 course helper that automates project directory structure for weekly assignments.

### <span id="todo"></span>TO DO:

#### <span id="clean"></span><a href="#clean">clean</a>
- [ ] Make a script to run for all projects accross IdeaProjects, Projects, and whatever else. will make use of <a href="#inv">inv</a> and <a href="#pkgs">pkgs</a> to discover and bulk remove all large files (specificaly libraries) that could easily be added back later with their package manager, as well as create a cleaned.md file that details what it removed and how to get it back so that the restore script can do its job later

#### <span id="todo-ec2"></span><a href="#ec2">ec2</a>
- [ ] Make more secure. Involve age and sops

#### <span id="restore"></span><a href="#restore">restore</a>
- [ ] Make a script that parses information from a cleaned.md file in the current project directory to determin and execute the proper steps in getting the project back up and running

#### <span id="todo-treebat"></span><a href="#treebat">treebat</a>
- [ ] Add large file safety checks, improve .gitignore handling