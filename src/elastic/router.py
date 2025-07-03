import pkg_resources

for dist in pkg_resources.working_set:
    print(f"{dist.project_name}=={dist.version}")
    print(pkg_resources.get_distribution(dist.project_name)._get_metadata("METADATA"))
    print("-" * 80)
