# Cozy Studio

Version control allows you to manage and track changes in a project. It provides project history, safety, and an easy way to collaborate with other individuals. Cozy studio brings the ease and safety of *git* to Blender.

Control the history and versioing of your .blend projects, know who committed what, where and when. Easily revert changes, checkout previous iterations of a project, merge and rebase updates, all in the comfort of the Blender ui.

# How does it work? 
Other Blender version control systems rely on storing copies of .blend files (autosave), or manually recording the inputs of a user. These methods are flakey, bulky, and can lead to discontinuity in action/commit history.

Cozy Studio uses a different approach: It uses Blenders *datablock* system by serializing individual data blocks into json files, storing them in a git repo, and allowing for seamless desearialization back into blender when the user requires (checking out a previous commit, opening the file).

This system works completely independently from Blender's autosave system, but crucially doesn't overstep it. Your productivity is peak when using autosave along side Cozy Studios git system.

# Why build this?
I have first hand experience building out large scale projects in blender and seeing where things fall apart. Clients are demanding, .blend file versions are hard to keep track of. Git doesn't help because it's complicated to store large volumes of .blend files. Collaborating with a team of creators is difficult without a version control system.

I saw first hand how hard blender development pipelines can be in large scale projects. My hope is that this will ease those pain points and allow for larger adoption of blender in studio and freelancing scenes.
