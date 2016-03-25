/*
Package module provides functions for interacting with modules.

The appengine package contains functions that report the identity of the app,
including the module name.
*/
package module

import (
	"appengine"
	pb "appengine_internal/modules"
)

// List returns the names of modules belonging to this application.
func List(c appengine.Context) ([]string, error) {
	req := &pb.GetModulesRequest{}
	res := &pb.GetModulesResponse{}
	err := c.Call("modules", "GetModules", req, res, nil)
	return res.Module, err
}

// NumInstances returns the number of instances of the given module/version.
// If either argument is the empty string it means the default.
func NumInstances(c appengine.Context, module, version string) (int, error) {
	req := &pb.GetNumInstancesRequest{}
	if module != "" {
		req.Module = &module
	}
	if version != "" {
		req.Version = &version
	}
	res := &pb.GetNumInstancesResponse{}

	if err := c.Call("modules", "GetNumInstances", req, res, nil); err != nil {
		return 0, err
	}
	return int(*res.Instances), nil
}
